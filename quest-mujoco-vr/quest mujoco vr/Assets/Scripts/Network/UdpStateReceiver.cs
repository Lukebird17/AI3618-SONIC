using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using SonicMujocoVr.Core;
using UnityEngine;

namespace SonicMujocoVr.Network
{
    public class UnityMainThreadDispatcher : MonoBehaviour
    {
        private static readonly Queue<Action> Queue = new();
        public static void Enqueue(Action action)
        {
            lock (Queue)
                Queue.Enqueue(action);
        }

        private void Update()
        {
            while (true)
            {
                Action a = null;
                lock (Queue)
                {
                    if (Queue.Count == 0)
                        break;
                    a = Queue.Dequeue();
                }
                a?.Invoke();
            }
        }
    }

    public class UdpStateReceiver : MonoBehaviour
    {
        [SerializeField] private int listenPort = 17771;
        public event Action<string> OnJsonReceived;

        private UdpClient _client;
        private string _pending;
        private bool _hasPending;
        private int _packetCount;

        private void OnEnable()
        {
            try
            {
                _client = new UdpClient(listenPort);
                _client.EnableBroadcast = true;
                _client.BeginReceive(OnReceive, null);
                _packetCount = 0;
                Debug.Log($"[UdpStateReceiver] Listening UDP {listenPort} (need Windows unity_udp_relay.ps1 + T4)");
            }
            catch (Exception e)
            {
                Debug.LogError($"[UdpStateReceiver] {e.Message}");
            }
        }

        private void OnDisable()
        {
            _client?.Close();
            _client = null;
        }

        private void Update()
        {
            if (!_hasPending)
                return;
            _hasPending = false;
            var json = _pending;
            _pending = null;
            if (!string.IsNullOrEmpty(json))
                OnJsonReceived?.Invoke(json);
        }

        private void OnReceive(IAsyncResult ar)
        {
            if (_client == null)
                return;
            try
            {
                var remote = new IPEndPoint(IPAddress.Any, 0);
                var data = _client.EndReceive(ar, ref remote);
                var json = Encoding.UTF8.GetString(data);
                UnityMainThreadDispatcher.Enqueue(() =>
                {
                    _pending = json;
                    _hasPending = true;
                    _packetCount++;
                    if (_packetCount == 1)
                        Debug.Log($"[UdpStateReceiver] First packet ({json.Length} bytes) — data path OK");
                });
            }
            catch (ObjectDisposedException) { return; }
            catch (Exception e)
            {
                Debug.LogWarning($"[UdpStateReceiver] {e.Message}");
            }
            finally
            {
                _client?.BeginReceive(OnReceive, null);
            }
        }
    }
}
