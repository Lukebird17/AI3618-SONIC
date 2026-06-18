using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

namespace SonicQuestMirror.Network
{
    /// <summary>
    /// Receives JSON UDP packets from sonic-bridge (port 17771).
    /// </summary>
    public class UdpStateReceiver : MonoBehaviour
    {
        [SerializeField] private int listenPort = 17771;

        public event Action<string> OnJsonReceived;

        private UdpClient _client;
        private IPEndPoint _any;
        private string _latestJson;
        private bool _hasPendingJson;

        private void OnEnable()
        {
            try
            {
                _any = new IPEndPoint(IPAddress.Any, listenPort);
                _client = new UdpClient(listenPort);
                _client.EnableBroadcast = true;
                _client.BeginReceive(OnReceive, null);
                Debug.Log($"[UdpStateReceiver] Listening on {listenPort}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[UdpStateReceiver] Failed to bind: {e.Message}");
            }
        }

        private void OnDisable()
        {
            _client?.Close();
            _client = null;
            _latestJson = null;
            _hasPendingJson = false;
        }

        private void Update()
        {
            if (!_hasPendingJson)
                return;

            _hasPendingJson = false;
            var json = _latestJson;
            _latestJson = null;
            if (!string.IsNullOrEmpty(json))
                OnJsonReceived?.Invoke(json);
        }

        private void OnReceive(IAsyncResult ar)
        {
            if (_client == null) return;
            try
            {
                var remote = new IPEndPoint(IPAddress.Any, 0);
                var data = _client.EndReceive(ar, ref remote);
                var json = Encoding.UTF8.GetString(data);
                UnityMainThreadDispatcher.Enqueue(() =>
                {
                    _latestJson = json;
                    _hasPendingJson = true;
                });
            }
            catch (ObjectDisposedException) { return; }
            catch (Exception e)
            {
                Debug.LogWarning($"[UdpStateReceiver] {e.Message}");
            }
            finally
            {
                if (_client != null)
                    _client.BeginReceive(OnReceive, null);
            }
        }
    }
}
