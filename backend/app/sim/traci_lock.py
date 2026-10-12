import threading
# Simulation updates can call helpers that also access TraCI on the same thread.
traci_lock = threading.RLock()
