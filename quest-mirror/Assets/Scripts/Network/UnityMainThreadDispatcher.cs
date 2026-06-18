using System.Collections.Generic;
using UnityEngine;

namespace SonicQuestMirror.Network
{
    /// <summary>
    /// Runs actions on Unity main thread from UDP callback thread.
    /// </summary>
    public class UnityMainThreadDispatcher : MonoBehaviour
    {
        private static readonly Queue<System.Action> Queue = new();
        private static UnityMainThreadDispatcher _instance;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Bootstrap()
        {
            if (_instance != null) return;
            var go = new GameObject("UnityMainThreadDispatcher");
            DontDestroyOnLoad(go);
            _instance = go.AddComponent<UnityMainThreadDispatcher>();
        }

        public static void Enqueue(System.Action action)
        {
            lock (Queue)
            {
                Queue.Enqueue(action);
            }
        }

        private void Update()
        {
            while (true)
            {
                System.Action action;
                lock (Queue)
                {
                    if (Queue.Count == 0) break;
                    action = Queue.Dequeue();
                }
                action?.Invoke();
            }
        }
    }
}
