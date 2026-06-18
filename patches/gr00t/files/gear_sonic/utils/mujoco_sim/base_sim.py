"""MuJoCo simulation environment and loop for the G1 (and H1) humanoid robots.

DefaultEnv owns the MuJoCo model/data, computes PD torques from Unitree SDK
commands, steps physics, and publishes observations back via the SDK bridge.
BaseSimulator wraps DefaultEnv with rate-limiting and viewer/image update loops.
"""

import os
import pathlib
from pathlib import Path
import pickle
import tempfile
from threading import Lock, Thread
import time
from typing import Dict
import xml.etree.ElementTree as ET

import mujoco
import mujoco.viewer
import numpy as np
from scipy.spatial.transform import Rotation

from gear_sonic.utils.mujoco_sim.metric_utils import check_contact, check_height
from gear_sonic.utils.mujoco_sim.sim_utils import get_subtree_body_names
from gear_sonic.utils.mujoco_sim.unitree_sdk2py_bridge import ElasticBand, UnitreeSdk2Bridge
from gear_sonic.utils.mujoco_sim.robot import Robot

GEAR_SONIC_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class DefaultEnv:
    """Base environment class that handles simulation environment setup and step"""

    def __init__(
        self,
        config: Dict[str, any],
        env_name: str = "default",
        camera_configs: Dict[str, any] = {},
        onscreen: bool = False,
        offscreen: bool = False,
        enable_image_publish: bool = False,
    ):
        self.config = config
        self.env_name = env_name
        self.robot = Robot(self.config)
        self.num_body_dof = self.robot.NUM_JOINTS
        self.num_hand_dof = self.robot.NUM_HAND_JOINTS
        self.sim_dt = self.config["SIMULATE_DT"]
        self.obs = None
        self.torques = np.zeros(self.num_body_dof + self.num_hand_dof * 2)
        self.torque_limit = np.array(self.robot.MOTOR_EFFORT_LIMIT_LIST)
        self.camera_configs = camera_configs

        self.reward_lock = Lock()
        self.unitree_bridge = None
        self.onscreen = onscreen
        self._band_gradual_release = False
        self._band_release_wait_log_t = 0.0
        self._session_reset_log_t = 0.0

        self.init_scene()
        self.last_reward = 0

        self.offscreen = offscreen
        if self.offscreen:
            self.init_renderers()
        self.image_dt = self.config.get("IMAGE_DT", 0.033333)
        self.image_publish_process = None

    def start_image_publish_subprocess(self, start_method: str = "spawn", camera_port: int = 5555):
        from gear_sonic.utils.mujoco_sim.image_publish_utils import ImagePublishProcess

        if len(self.camera_configs) == 0:
            print(
                "Warning: No camera configs provided, image publishing subprocess will not be started"
            )
            return
        start_method = self.config.get("MP_START_METHOD", "spawn")
        self.image_publish_process = ImagePublishProcess(
            camera_configs=self.camera_configs,
            image_dt=self.image_dt,
            zmq_port=camera_port,
            start_method=start_method,
            verbose=self.config.get("verbose", False),
        )
        self.image_publish_process.start_process()

    def _get_dof_indices_by_class(self):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".xml") as f:
            mujoco.mj_saveLastXML(f.name, self.mj_model)
            temp_xml_path = f.name

        try:
            tree = ET.parse(temp_xml_path)
            root = tree.getroot()

            joint_class_map = {}
            for joint_element in root.findall(".//joint[@class]"):
                joint_name = joint_element.get("name")
                joint_class = joint_element.get("class")
                if joint_name and joint_class:
                    joint_id = mujoco.mj_name2id(
                        self.mj_model, mujoco.mjtObj.mjOBJ_JOINT, joint_name
                    )
                    if joint_id != -1:
                        dof_adr = self.mj_model.jnt_dofadr[joint_id]
                        if joint_class not in joint_class_map:
                            joint_class_map[joint_class] = []
                        joint_class_map[joint_class].append(dof_adr)
        finally:
            os.remove(temp_xml_path)

        return joint_class_map

    def _get_default_dof_properties(self):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".xml") as f:
            mujoco.mj_saveLastXML(f.name, self.mj_model)
            temp_xml_path = f.name

        try:
            tree = ET.parse(temp_xml_path)
            root = tree.getroot()

            default_dof_properties = {}
            for default_element in root.findall(".//default/default[@class]"):
                class_name = default_element.get("class")
                joint_element = default_element.find("joint")
                if class_name and joint_element is not None:
                    properties = {}
                    if "damping" in joint_element.attrib:
                        properties["damping"] = float(joint_element.get("damping"))
                    if "armature" in joint_element.attrib:
                        properties["armature"] = float(joint_element.get("armature"))
                    if "frictionloss" in joint_element.attrib:
                        properties["frictionloss"] = float(joint_element.get("frictionloss"))

                    if properties:
                        default_dof_properties[class_name] = properties
        finally:
            os.remove(temp_xml_path)

        return default_dof_properties

    def init_scene(self):
        """Initialize the default robot scene"""
        xml_path = str(pathlib.Path(GEAR_SONIC_ROOT) / self.config["ROBOT_SCENE"])
        self.mj_model = mujoco.MjModel.from_xml_path(xml_path)
        self.mj_data = mujoco.MjData(self.mj_model)
        self.mj_model.opt.timestep = self.sim_dt
        self._tune_physics_solver()
        self.torso_index = mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_BODY, "torso_link")
        self.root_body = "pelvis"
        self.root_body_id = self.mj_model.body(self.root_body).id

        self.joint_class_map = self._get_dof_indices_by_class()

        self.perform_sysid_search = self.config.get("perform_sysid_search", False)

        # Check for static root link (fixed base)
        self.use_floating_root_link = "floating_base_joint" in [
            self.mj_model.joint(i).name for i in range(self.mj_model.njnt)
        ]
        self.use_constrained_root_link = "constrained_base_joint" in [
            self.mj_model.joint(i).name for i in range(self.mj_model.njnt)
        ]

        # MuJoCo qpos/qvel arrays start with root DOFs before joint DOFs:
        # floating base has 7 qpos (pos + quat) and 6 qvel (lin + ang velocity)
        if self.use_floating_root_link:
            self.qpos_offset = 7
            self.qvel_offset = 6
        else:
            if self.use_constrained_root_link:
                self.qpos_offset = 1
                self.qvel_offset = 1
            else:
                raise ValueError(
                    "No root link found --"
                    "The absolute static root will make the simulation unstable."
                )

        # Enable the elastic band (SONIC default: suspend at z=1 until deploy takes over)
        if self.config["ENABLE_ELASTIC_BAND"] and self.use_floating_root_link:
            self.elastic_band = ElasticBand()
            if "g1" in self.config["ROBOT_TYPE"]:
                if self.config["enable_waist"]:
                    self.band_attached_link = self.mj_model.body("pelvis").id
                else:
                    self.band_attached_link = self.mj_model.body("torso_link").id
            elif "h1" in self.config["ROBOT_TYPE"]:
                self.band_attached_link = self.mj_model.body("torso_link").id
            else:
                self.band_attached_link = self.mj_model.body("base_link").id

            if self.onscreen:
                self.viewer = mujoco.viewer.launch_passive(
                    self.mj_model,
                    self.mj_data,
                    key_callback=self.elastic_band.MujuocoKeyCallback,
                    show_left_ui=False,
                    show_right_ui=False,
                )
            else:
                mujoco.mj_forward(self.mj_model, self.mj_data)
                self.viewer = None
        else:
            self.elastic_band = None
            if self.onscreen:
                self.viewer = mujoco.viewer.launch_passive(
                    self.mj_model, self.mj_data, show_left_ui=False, show_right_ui=False
                )
            else:
                mujoco.mj_forward(self.mj_model, self.mj_data)
                self.viewer = None

        if self.viewer:
            self.viewer.cam.azimuth = 120
            self.viewer.cam.elevation = -30
            self.viewer.cam.distance = 2.0
            self.viewer.cam.lookat = np.array([0, 0, 0.5])
            self.viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
            self.viewer.cam.trackbodyid = self.mj_model.body("pelvis").id

        self.body_joint_index = []
        self.left_hand_index = []
        self.right_hand_index = []
        for i in range(self.mj_model.njnt):
            name = self.mj_model.joint(i).name
            if any(
                [
                    part_name in name
                    for part_name in ["hip", "knee", "ankle", "waist", "shoulder", "elbow", "wrist"]
                ]
            ):
                self.body_joint_index.append(i)
            elif "left_hand" in name:
                self.left_hand_index.append(i)
            elif "right_hand" in name:
                self.right_hand_index.append(i)

        assert len(self.body_joint_index) == self.robot.NUM_JOINTS
        assert len(self.left_hand_index) == self.robot.NUM_HAND_JOINTS
        assert len(self.right_hand_index) == self.robot.NUM_HAND_JOINTS

        self.body_joint_index = np.array(self.body_joint_index)
        self.left_hand_index = np.array(self.left_hand_index)
        self.right_hand_index = np.array(self.right_hand_index)

        if mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_BODY, "bottle_body") != -1:
            print(
                "[MuJoCo] 多任务实验台 — 宽台面 ~50cm 前："
                "左=红圆柱→白盘+绿收纳盒 | 中=绿瓶 | 右=蓝方块→蓝收纳盒 | 后=水龙头 | 前方绿区走路"
            )
            self._playground_tasks_done = set()
        elif mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_BODY, "cube_body") != -1:
            print(
                "[MuJoCo] 厨房台面场景 — 机器人正前方 ~30cm："
                "蓝方块(右) | 红圆柱+白盘(左) | 水槽+水龙头(后) | 前方绿区走路"
            )
            self._playground_tasks_done = set()

    def _is_quest_manip_scene(self) -> bool:
        scene = str(self.config.get("ROBOT_SCENE", ""))
        return any(
            k in scene
            for k in (
                "scene_quest_playground",
                "scene_quest_multitask",
                "quest_playground",
                "quest_multitask",
            )
        )

    def _tune_physics_solver(self) -> None:
        """CG solver avoids Newton Hessian factorization failures during hand-object contact."""
        if not self._is_quest_manip_scene():
            return
        self.mj_model.opt.solver = mujoco.mjtSolver.mjSOL_CG
        self.mj_model.opt.iterations = max(int(self.mj_model.opt.iterations), 80)
        self.mj_model.opt.tolerance = max(float(self.mj_model.opt.tolerance), 1e-5)
        self.mj_model.opt.impratio = max(float(self.mj_model.opt.impratio), 10.0)
        print(
            "[MuJoCo] 抓取场景物理: CG solver "
            f"(iter={self.mj_model.opt.iterations}, impratio={self.mj_model.opt.impratio})"
        )
        self._tune_hand_contact_geoms()

    def _tune_hand_contact_geoms(self) -> None:
        """Softer finger/object contacts — reduces grasp blow-up in MuJoCo."""
        for gid in range(self.mj_model.ngeom):
            name = mujoco.mj_id2name(self.mj_model, mujoco.mjtObj.mjOBJ_GEOM, gid) or ""
            if "hand" not in name and name not in ("apple", "cube", "bottle"):
                continue
            self.mj_model.geom_margin[gid] = max(float(self.mj_model.geom_margin[gid]), 0.002)
            self.mj_model.geom_solref[gid, 0] = max(float(self.mj_model.geom_solref[gid, 0]), 0.04)
            self.mj_model.geom_solref[gid, 1] = min(float(self.mj_model.geom_solref[gid, 1]), 1.0)

    def init_renderers(self):
        self.renderers = {}
        for camera_name, camera_config in self.camera_configs.items():
            renderer = mujoco.Renderer(
                self.mj_model, height=camera_config["height"], width=camera_config["width"]
            )
            self.renderers[camera_name] = renderer

    def compute_body_torques(self) -> np.ndarray:
        """Track deploy lowcmd PD only (SONIC default — no sim-side stance hold)."""
        body_torques = np.zeros(self.num_body_dof)
        if self.unitree_bridge is not None and self.unitree_bridge.low_cmd:
            for i in range(self.unitree_bridge.num_body_motor):
                qpos_adr = self.mj_model.jnt_qposadr[self.body_joint_index[i]]
                qvel_adr = self.mj_model.jnt_dofadr[self.body_joint_index[i]]
                if self.unitree_bridge.use_sensor:
                    body_torques[i] = (
                        self.unitree_bridge.low_cmd.motor_cmd[i].tau
                        + self.unitree_bridge.low_cmd.motor_cmd[i].kp
                        * (self.unitree_bridge.low_cmd.motor_cmd[i].q - self.mj_data.sensordata[i])
                        + self.unitree_bridge.low_cmd.motor_cmd[i].kd
                        * (
                            self.unitree_bridge.low_cmd.motor_cmd[i].dq
                            - self.mj_data.sensordata[i + self.unitree_bridge.num_body_motor]
                        )
                    )
                else:
                    body_torques[i] = (
                        self.unitree_bridge.low_cmd.motor_cmd[i].tau
                        + self.unitree_bridge.low_cmd.motor_cmd[i].kp
                        * (
                            self.unitree_bridge.low_cmd.motor_cmd[i].q
                            - self.mj_data.qpos[qpos_adr]
                        )
                        + self.unitree_bridge.low_cmd.motor_cmd[i].kd
                        * (
                            self.unitree_bridge.low_cmd.motor_cmd[i].dq
                            - self.mj_data.qvel[qvel_adr]
                        )
                    )
        return body_torques

    def reset_to_calibration_ready(self, notify_manager: bool = True) -> None:
        """Reset sim to pre-calibration: default pose + elastic band holding at z=1."""
        mujoco.mj_resetData(self.mj_model, self.mj_data)
        if self.elastic_band:
            self.elastic_band.enable = True
            self.elastic_band.length = 0
            self._band_gradual_release = False
            if hasattr(self, "band_attached_link"):
                self.mj_data.xfrc_applied[self.band_attached_link] = np.zeros(6)
        try:
            Path("/tmp/sonic_mujoco_release_band").unlink(missing_ok=True)
        except OSError:
            pass
        mujoco.mj_forward(self.mj_model, self.mj_data)
        self.fall = False
        self._playground_tasks_done = set()
        if notify_manager:
            try:
                Path("/tmp/sonic_manager_session_reset").touch()
            except OSError:
                pass
        print(
            "[MuJoCo] 全场复位 — 机器人默认站姿 + 弹力绳 ON + 物件回初始位；"
            "T3: B 校准 → Y 启动"
        )

    def _maybe_session_reset(self) -> None:
        flag = Path("/tmp/sonic_mujoco_session_reset")
        if not flag.exists():
            return
        try:
            flag.unlink(missing_ok=True)
        except OSError:
            pass
        self.reset_to_calibration_ready(notify_manager=True)

    def _deploy_has_leg_support(self) -> bool:
        if self.unitree_bridge is None or not self.unitree_bridge.low_cmd_received:
            return False
        active = sum(
            1
            for i in range(min(12, self.unitree_bridge.num_body_motor))
            if self.unitree_bridge.low_cmd.motor_cmd[i].kp > 10.0
        )
        return active >= 6

    def _maybe_release_elastic_band(self) -> None:
        if not self.elastic_band or not self.elastic_band.enable:
            return

        flag = Path("/tmp/sonic_mujoco_release_band")
        if flag.exists() and not self._band_gradual_release:
            if not self._deploy_has_leg_support():
                now = time.time()
                if now - self._band_release_wait_log_t > 2.0:
                    print(
                        "[MuJoCo] 等待 deploy 腿 PD 再放下 — 请先 T2 Init done "
                        "(source wsl_dds_env.sh)"
                    )
                    self._band_release_wait_log_t = now
                return
            try:
                flag.unlink(missing_ok=True)
            except OSError:
                pass
            self._band_gradual_release = True
            print("[MuJoCo] 缓慢放下：deploy 已接管，elastic band 降高中…")

        if not self._band_gradual_release:
            return

        # SONIC 原版用 MuJoCo 7/8 调 length；这里自动从 z≈1 降到站立高度再关 band
        self.elastic_band.length -= 0.001
        if self.elastic_band.length <= -0.18:
            self.elastic_band.enable = False
            self._band_gradual_release = False
            if hasattr(self, "band_attached_link"):
                self.mj_data.xfrc_applied[self.band_attached_link] = np.zeros(6)
            print("[MuJoCo] Elastic band OFF — 已落地，policy 持姿")

    def get_head_pose(self) -> np.ndarray:
        root_pos = self.mj_data.body("torso_link").xpos.copy()
        # Reorder quaternion from MuJoCo [w,x,y,z] to scipy [x,y,z,w]
        root_quat = self.mj_data.body("torso_link").xquat.copy()[[1, 2, 3, 0]]
        head_pos = root_pos + Rotation.from_quat(root_quat).apply(np.array([0.0, 0.0, -0.044]))
        return np.concatenate((head_pos, root_quat))

    def get_root_vel(self) -> np.ndarray:
        return self.mj_data.qvel[:6]

    def compute_hand_torques(self) -> np.ndarray:
        left_hand_torques = np.zeros(self.num_hand_dof)
        right_hand_torques = np.zeros(self.num_hand_dof)
        if self.unitree_bridge is not None and self.unitree_bridge.low_cmd:
            for i in range(self.unitree_bridge.num_hand_motor):
                left_hand_torques[i] = (
                    self.unitree_bridge.left_hand_cmd.motor_cmd[i].tau
                    + self.unitree_bridge.left_hand_cmd.motor_cmd[i].kp
                    * (
                        self.unitree_bridge.left_hand_cmd.motor_cmd[i].q
                        - self.mj_data.qpos[self.left_hand_index[i] + self.qpos_offset - 1]
                    )
                    + self.unitree_bridge.left_hand_cmd.motor_cmd[i].kd
                    * (
                        self.unitree_bridge.left_hand_cmd.motor_cmd[i].dq
                        - self.mj_data.qvel[self.left_hand_index[i] + self.qvel_offset - 1]
                    )
                )
                right_hand_torques[i] = (
                    self.unitree_bridge.right_hand_cmd.motor_cmd[i].tau
                    + self.unitree_bridge.right_hand_cmd.motor_cmd[i].kp
                    * (
                        self.unitree_bridge.right_hand_cmd.motor_cmd[i].q
                        - self.mj_data.qpos[self.right_hand_index[i] + self.qpos_offset - 1]
                    )
                    + self.unitree_bridge.right_hand_cmd.motor_cmd[i].kd
                    * (
                        self.unitree_bridge.right_hand_cmd.motor_cmd[i].dq
                        - self.mj_data.qvel[self.right_hand_index[i] + self.qvel_offset - 1]
                    )
                )
        return np.concatenate((left_hand_torques, right_hand_torques))

    def compute_body_qpos(self) -> np.ndarray:
        body_qpos = np.zeros(self.num_body_dof)
        if self.unitree_bridge is not None and self.unitree_bridge.low_cmd:
            for i in range(self.unitree_bridge.num_body_motor):
                body_qpos[i] = self.unitree_bridge.low_cmd.motor_cmd[i].q
        return body_qpos

    def compute_hand_qpos(self) -> np.ndarray:
        hand_qpos = np.zeros(self.num_hand_dof * 2)
        if self.unitree_bridge is not None and self.unitree_bridge.low_cmd:
            for i in range(self.unitree_bridge.num_hand_motor):
                hand_qpos[i] = self.unitree_bridge.left_hand_cmd.motor_cmd[i].q
                hand_qpos[i + self.num_hand_dof] = self.unitree_bridge.right_hand_cmd.motor_cmd[i].q
        return hand_qpos

    def prepare_obs(self) -> Dict[str, any]:
        obs = {}
        if self.use_floating_root_link:
            obs["floating_base_pose"] = self.mj_data.qpos[:7]
            obs["floating_base_vel"] = self.mj_data.qvel[:6]
            obs["floating_base_acc"] = self.mj_data.qacc[:6]
        else:
            obs["floating_base_pose"] = np.zeros(7)
            obs["floating_base_vel"] = np.zeros(6)
            obs["floating_base_acc"] = np.zeros(6)

        obs["secondary_imu_quat"] = self.mj_data.xquat[self.torso_index]

        pose = np.zeros(13)
        torso_link = self.mj_model.body("torso_link").id
        # mj_objectVelocity returns [ang_vel, lin_vel]; swap to [lin_vel, ang_vel]
        mujoco.mj_objectVelocity(
            self.mj_model, self.mj_data, mujoco.mjtObj.mjOBJ_BODY, torso_link, pose[7:13], 1
        )
        pose[7:10], pose[10:13] = (
            pose[10:13],
            pose[7:10].copy(),
        )
        obs["secondary_imu_vel"] = pose[7:13]

        obs["body_q"] = self.mj_data.qpos[self.body_joint_index + 7 - 1]
        obs["body_dq"] = self.mj_data.qvel[self.body_joint_index + 6 - 1]
        obs["body_ddq"] = self.mj_data.qacc[self.body_joint_index + 6 - 1]
        obs["body_tau_est"] = self.mj_data.actuator_force[self.body_joint_index - 1]
        if self.num_hand_dof > 0:
            obs["left_hand_q"] = self.mj_data.qpos[self.left_hand_index + self.qpos_offset - 1]
            obs["left_hand_dq"] = self.mj_data.qvel[self.left_hand_index + self.qvel_offset - 1]
            obs["left_hand_ddq"] = self.mj_data.qacc[self.left_hand_index + self.qvel_offset - 1]
            obs["left_hand_tau_est"] = self.mj_data.actuator_force[self.left_hand_index - 1]
            obs["right_hand_q"] = self.mj_data.qpos[self.right_hand_index + self.qpos_offset - 1]
            obs["right_hand_dq"] = self.mj_data.qvel[self.right_hand_index + self.qvel_offset - 1]
            obs["right_hand_ddq"] = self.mj_data.qacc[self.right_hand_index + self.qvel_offset - 1]
            obs["right_hand_tau_est"] = self.mj_data.actuator_force[self.right_hand_index - 1]
        obs["time"] = self.mj_data.time
        return obs

    def sim_step(self):
        self.obs = self.prepare_obs()
        self.unitree_bridge.PublishLowState(self.obs)
        if self.unitree_bridge.joystick:
            self.unitree_bridge.PublishWirelessController()
        self._maybe_session_reset()
        self._maybe_release_elastic_band()
        if self.elastic_band:
            if self.elastic_band.enable and self.use_floating_root_link:
                pose = np.concatenate(
                    [
                        self.mj_data.xpos[self.band_attached_link],
                        self.mj_data.xquat[self.band_attached_link],
                        np.zeros(6),
                    ]
                )
                mujoco.mj_objectVelocity(
                    self.mj_model,
                    self.mj_data,
                    mujoco.mjtObj.mjOBJ_BODY,
                    self.band_attached_link,
                    pose[7:13],
                    0,
                )
                pose[7:10], pose[10:13] = pose[10:13], pose[7:10].copy()
                self.mj_data.xfrc_applied[self.band_attached_link] = self.elastic_band.Advance(pose)
            else:
                self.mj_data.xfrc_applied[self.band_attached_link] = np.zeros(6)
        body_torques = self.compute_body_torques()
        hand_torques = self.compute_hand_torques()
        # -1: actuator array is 0-based while joint indices from the model are 1-based
        self.torques[self.body_joint_index - 1] = body_torques
        if self.num_hand_dof > 0:
            self.torques[self.left_hand_index - 1] = hand_torques[: self.num_hand_dof]
            self.torques[self.right_hand_index - 1] = hand_torques[self.num_hand_dof :]

        self.torques = np.clip(self.torques, -self.torque_limit, self.torque_limit)

        if self.config["FREE_BASE"]:
            # Prepend 6 zeros for the floating-base root DOF actuators
            self.mj_data.ctrl = np.concatenate((np.zeros(6), self.torques))
        else:
            self.mj_data.ctrl = self.torques
        self._safe_mj_step()

        self.check_fall()

    @staticmethod
    def _physics_recoverable(exc: Exception) -> bool:
        msg = str(exc)
        return any(
            k in msg
            for k in (
                "FactorizeHessian",
                "rank-deficient",
                "stack overflow",
                "stackAlloc",
                "arena memory",
            )
        )

    def _safe_mj_forward(self) -> bool:
        try:
            mujoco.mj_forward(self.mj_model, self.mj_data)
            return True
        except Exception as exc:
            if self._physics_recoverable(exc):
                return False
            raise

    def _mj_step_with_solver(self, solver: int) -> None:
        old_solver = int(self.mj_model.opt.solver)
        self.mj_model.opt.solver = solver
        try:
            mujoco.mj_step(self.mj_model, self.mj_data)
        finally:
            self.mj_model.opt.solver = old_solver

    def _physics_recover_from(self, exc: Exception) -> None:
        self._physics_bad_streak = getattr(self, "_physics_bad_streak", 0) + 1
        now = time.time()
        if now - getattr(self, "_last_hessian_log_t", 0.0) >= 3.0:
            self._last_hessian_log_t = now
            streak = self._physics_bad_streak
            print(
                f"[MuJoCo] 物理异常，恢复状态并继续 ({streak} 连续): {exc}"
            )

        qpos = self.mj_data.qpos.copy()
        qvel = self.mj_data.qvel.copy()
        # 只衰减线速度，保留角速度/关节速度，避免把平衡“阻尼”掉
        if self.use_floating_root_link:
            qvel[0:3] *= 0.7
        mujoco.mj_resetData(self.mj_model, self.mj_data)
        self.mj_data.qpos[:] = qpos
        self.mj_data.qvel[:] = qvel

        if self._safe_mj_forward():
            return

        # 降级到 PGS（不分解 Hessian），且必须保留地面接触
        try:
            self._mj_step_with_solver(int(mujoco.mjtSolver.mjSOL_PGS))
        except Exception as fallback_exc:
            if not self._physics_recoverable(fallback_exc):
                raise
            self._physics_freeze = max(getattr(self, "_physics_freeze", 0), 3)
        self._skip_viewer_once = True

    def _safe_mj_step(self) -> None:
        """Step physics; recover from bad contact frames instead of killing the sim."""
        freeze = int(getattr(self, "_physics_freeze", 0))
        if freeze > 0:
            self._physics_freeze = freeze - 1
            self._safe_mj_forward()
            return

        try:
            mujoco.mj_step(self.mj_model, self.mj_data)
            self._physics_bad_streak = 0
        except Exception as exc:
            if not self._physics_recoverable(exc):
                raise
            self._physics_recover_from(exc)

    def apply_perturbation(self, key):
        perturbation_x_body = 0.0
        perturbation_y_body = 0.0
        if key == "up":
            perturbation_x_body = 1.0
        elif key == "down":
            perturbation_x_body = -1.0
        elif key == "left":
            perturbation_y_body = 1.0
        elif key == "right":
            perturbation_y_body = -1.0

        vel_body = np.array([perturbation_x_body, perturbation_y_body, 0.0])
        vel_world = np.zeros(3)
        base_quat = self.mj_data.qpos[3:7]
        mujoco.mju_rotVecQuat(vel_world, vel_body, base_quat)

        self.mj_data.qvel[0] += vel_world[0]
        self.mj_data.qvel[1] += vel_world[1]
        mujoco.mj_forward(self.mj_model, self.mj_data)

    def update_viewer(self):
        if self.viewer is not None:
            if getattr(self, "_skip_viewer_once", False):
                self._skip_viewer_once = False
                return
            self.viewer.sync()

    def update_viewer_camera(self):
        if self.viewer is not None:
            if self.viewer.cam.type == mujoco.mjtCamera.mjCAMERA_TRACKING:
                self.viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            else:
                self.viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING

    def _filter_existing_bodies(self, names: list[str]) -> list[str]:
        return [n for n in names if self._mj_body_exists(n)]

    def update_reward(self):
        """Scene mini-tasks for quest_playground (prints once per completion)."""
        reward = 0
        done: set[str] = getattr(self, "_playground_tasks_done", set())

        def _mark(task_id: str, message: str) -> None:
            nonlocal reward
            if task_id not in done:
                done.add(task_id)
                reward = 1
                print(f"[Task] ✅ {message}")
                print("[Task] 按 Quest A 或 ~/vr/scripts/reset_sonic_session.sh 可手动全场复位")

        if self._mj_body_exists("cube_body"):
            right_hand = self._filter_existing_bodies(
                [
                    "right_hand_thumb_2_link",
                    "right_hand_middle_1_link",
                    "right_hand_index_1_link",
                    "right_wrist_yaw_link",
                ]
            )
            if right_hand and check_contact(
                self.mj_model, self.mj_data, right_hand, "cube_body"
            ) and check_height(self.mj_model, self.mj_data, "cube", 0.86, 2.0):
                _mark("cube_lift", "抓起蓝色方块并抬离台面")

        if self._mj_body_exists("apple_body") and self._mj_body_exists("plate_body"):
            if check_contact(self.mj_model, self.mj_data, "apple_body", "plate_body"):
                _mark("apple_plate", "红色圆柱放到白盘上")

        if self._mj_body_exists("bottle_body"):
            hands = self._filter_existing_bodies(
                [
                    "left_wrist_yaw_link",
                    "right_wrist_yaw_link",
                    "left_hand_index_1_link",
                    "right_hand_index_1_link",
                    "left_hand_thumb_2_link",
                    "right_hand_thumb_2_link",
                ]
            )
            if hands and check_contact(
                self.mj_model, self.mj_data, hands, "bottle_body"
            ) and check_height(self.mj_model, self.mj_data, "bottle", 0.88, 2.0):
                _mark("bottle_lift", "抓起绿色瓶子并抬离台面")

        if self._mj_body_exists("bin_blue_body") and self._mj_body_exists("cube_body"):
            if check_contact(self.mj_model, self.mj_data, "cube_body", "bin_blue_body"):
                _mark("cube_bin", "蓝色方块放入蓝色收纳盒")

        if self._mj_body_exists("bin_green_body") and self._mj_body_exists("apple_body"):
            if check_contact(self.mj_model, self.mj_data, "apple_body", "bin_green_body"):
                _mark("apple_bin", "红色圆柱放入绿色收纳盒")

        if self._mj_body_exists("faucet_body"):
            hands = self._filter_existing_bodies(
                [
                    "left_wrist_yaw_link",
                    "right_wrist_yaw_link",
                    "left_hand_index_1_link",
                    "right_hand_index_1_link",
                    "left_hand_thumb_2_link",
                    "right_hand_thumb_2_link",
                ]
            )
            if hands and check_contact(self.mj_model, self.mj_data, hands, "faucet_body"):
                _mark("faucet_touch", "手碰到水龙头")

        if self._mj_site_exists("walk_goal") and self._mj_body_exists("pelvis"):
            goal_id = mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_SITE, "walk_goal")
            pelvis_id = self.mj_model.body("pelvis").id
            goal_xy = self.mj_model.site_pos[goal_id][:2]
            pelvis_xy = self.mj_data.xpos[pelvis_id][:2]
            if float(np.linalg.norm(pelvis_xy - goal_xy)) < 0.18:
                _mark("walk_goal", "走到绿色目标区（两黄锥之间）")

        self._playground_tasks_done = done
        with self.reward_lock:
            self.last_reward = reward

    def _mj_body_exists(self, name: str) -> bool:
        return mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_BODY, name) != -1

    def _mj_site_exists(self, name: str) -> bool:
        return mujoco.mj_name2id(self.mj_model, mujoco.mjtObj.mjOBJ_SITE, name) != -1

    def get_reward(self):
        with self.reward_lock:
            return self.last_reward

    def set_unitree_bridge(self, unitree_bridge):
        self.unitree_bridge = unitree_bridge

    def get_privileged_obs(self):
        return {}

    def update_render_caches(self):
        render_caches = {}
        for camera_name, camera_config in self.camera_configs.items():
            renderer = self.renderers[camera_name]
            if "params" in camera_config:
                renderer.update_scene(self.mj_data, camera=camera_config["params"])
            else:
                renderer.update_scene(self.mj_data, camera=camera_name)
            render_caches[camera_name + "_image"] = renderer.render()

        if self.image_publish_process is not None:
            self.image_publish_process.update_shared_memory(render_caches)

        return render_caches

    def handle_keyboard_button(self, key):
        if self.elastic_band:
            self.elastic_band.handle_keyboard_button(key)

        if key == "backspace":
            self.reset_to_calibration_ready()
        if key == "v":
            self.update_viewer_camera()
        if key in ["up", "down", "left", "right"]:
            self.apply_perturbation(key)

    def check_fall(self):
        self.fall = False
        if self.mj_data.qpos[2] < 0.2:
            self.fall = True
            now = time.time()
            if now - getattr(self, "_last_fall_log_t", 0.0) >= 3.0:
                self._last_fall_log_t = now
                print(f"Warning: Robot has fallen, height: {self.mj_data.qpos[2]:.3f} m")

        if self.fall:
            # Do not mj_resetData — that drops a suspended robot and loops "fallen" spam.
            pass

    def check_self_collision(self):
        robot_bodies = get_subtree_body_names(self.mj_model, self.mj_model.body(self.root_body).id)
        self_collision, contact_bodies = check_contact(
            self.mj_model, self.mj_data, robot_bodies, robot_bodies, return_all_contact_bodies=True
        )
        if self_collision:
            print(f"Warning: Self-collision detected: {contact_bodies}")
        return self_collision

    def reset(self):
        mujoco.mj_resetData(self.mj_model, self.mj_data)


class BaseSimulator:
    """Base simulator class that handles initialization and running of simulations"""

    def __init__(
        self, config: Dict[str, any], env_name: str = "default", redis_client=None, **kwargs
    ):
        self.config = config
        self.env_name = env_name
        self.redis_client = redis_client
        if self.redis_client is not None:
            self.redis_client.set("push_left_hand", "false")
            self.redis_client.set("push_right_hand", "false")
            self.redis_client.set("push_torso", "false")

        # Create rate objects
        self.sim_dt = self.config["SIMULATE_DT"]
        self.reward_dt = self.config.get("REWARD_DT", 0.05)
        self.image_dt = self.config.get("IMAGE_DT", 0.033333)
        self.viewer_dt = self.config.get("VIEWER_DT", 0.02)
        self.sim_realtime = bool(self.config.get("SIM_REALTIME", True))
        self._running = True
        self._last_viewer_sync = 0.0
        self._fps_last_report = time.time()
        self._fps_steps = 0

        self.robot = Robot(self.config)

        enable_fpv = kwargs.pop("enable_fpv_stream", False)
        fpv_port = int(kwargs.pop("fpv_port", 8765))
        fpv_hz = float(kwargs.pop("fpv_hz", 20.0))
        fpv_preview = bool(kwargs.pop("enable_fpv_preview", False))

        # Create the environment
        if env_name == "default":
            self.sim_env = DefaultEnv(config, env_name, **kwargs)
        else:
            raise ValueError(
                f"Invalid environment name: {env_name}. "
                f"Only 'default' is supported in this minimal build."
            )

        # DDS channel is initialized in run_sim_loop.SimWrapper.init_channel().
        self.init_unitree_bridge()
        self.sim_env.set_unitree_bridge(self.unitree_bridge)

        self.init_subscriber()
        self.init_publisher()

        self.fpv_server = None
        if enable_fpv:
            from gear_sonic.utils.mujoco_sim.fpv_mjpeg_server import FpvMjpegServer

            self.fpv_hz = fpv_hz
            self.fpv_server = FpvMjpegServer(
                port=fpv_port, enable_preview_window=fpv_preview
            )
            self.fpv_server.start()
        else:
            self.fpv_hz = 0.0

        self.sim_thread = None

    def start_as_thread(self):
        self.sim_thread = Thread(target=self.start)
        self.sim_thread.start()

    def start_image_publish_subprocess(self, start_method: str = "spawn", camera_port: int = 5555):
        self.sim_env.start_image_publish_subprocess(start_method, camera_port)

    def init_subscriber(self):
        pass

    def init_publisher(self):
        pass

    def init_unitree_bridge(self):
        self.unitree_bridge = UnitreeSdk2Bridge(self.config)
        if self.config["USE_JOYSTICK"]:
            self.unitree_bridge.SetupJoystick(
                device_id=self.config["JOYSTICK_DEVICE"], js_type=self.config["JOYSTICK_TYPE"]
            )

    def start(self):
        """Main simulation loop"""
        sim_cnt = 0
        ts = time.time()
        target_hz = 1.0 / max(self.sim_dt, 1e-6)
        print(
            f"[MuJoCo] sim_dt={self.sim_dt*1000:.1f}ms (~{target_hz:.0f}Hz) "
            f"viewer_dt={self.viewer_dt*1000:.0f}ms realtime={self.sim_realtime} "
            f"onscreen={self.sim_env.onscreen}"
        )

        try:
            while self._running and (
                (self.sim_env.viewer and self.sim_env.viewer.is_running())
                or (self.sim_env.viewer is None)
            ):
                step_start = time.monotonic()

                self.sim_env.sim_step()

                now = time.time()
                if now - ts > 1 / 10.0 and self.redis_client is not None:
                    head_pose = self.sim_env.get_head_pose()
                    self.redis_client.set("head_pos", pickle.dumps(head_pose[:3]))
                    self.redis_client.set("head_quat", pickle.dumps(head_pose[3:]))
                    ts = now

                if sim_cnt % int(self.reward_dt / self.sim_dt) == 0:
                    try:
                        self.sim_env.update_reward()
                    except Exception as exc:
                        print(f"[MuJoCo] update_reward 跳过本帧: {exc}")

                if sim_cnt % int(self.image_dt / self.sim_dt) == 0:
                    self.sim_env.update_render_caches()

                if (
                    self.fpv_server is not None
                    and self.fpv_hz > 0
                    and not getattr(self.sim_env, "_skip_viewer_once", False)
                    and sim_cnt % max(1, int(1.0 / (self.fpv_hz * self.sim_dt))) == 0
                ):
                    self.fpv_server.render_and_publish(
                        self.sim_env.mj_model, self.sim_env.mj_data
                    )

                # Physics rate limit (viewer sync must NOT slow sim — WSL GUI is slow)
                if self.sim_realtime:
                    elapsed = time.monotonic() - step_start
                    sleep_time = self.sim_dt - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                now_mono = time.monotonic()
                if (
                    self.sim_env.viewer is not None
                    and now_mono - self._last_viewer_sync >= self.viewer_dt
                ):
                    self._last_viewer_sync = now_mono
                    self.sim_env.update_viewer()

                sim_cnt += 1
                self._fps_steps += 1
                if now_mono - self._fps_last_report >= 5.0:
                    fps = self._fps_steps / (now_mono - self._fps_last_report)
                    print(f"[MuJoCo] physics FPS: {fps:.1f} (target ~{target_hz:.0f})")
                    self._fps_steps = 0
                    self._fps_last_report = now_mono
        except KeyboardInterrupt:
            print("Simulator interrupted by user.")
        finally:
            self.close()

    def __del__(self):
        self.close()

    def reset(self):
        self.sim_env.reset()

    def close(self):
        self._running = False
        try:
            if self.fpv_server is not None:
                self.fpv_server.stop()
            if self.sim_env.image_publish_process is not None:
                self.sim_env.image_publish_process.stop()
            if self.sim_env.viewer is not None:
                self.sim_env.viewer.close()
        except Exception as e:
            print(f"Warning during close: {e}")

    def get_privileged_obs(self):
        return self.sim_env.get_privileged_obs()

    def handle_keyboard_button(self, key):
        self.sim_env.handle_keyboard_button(key)
