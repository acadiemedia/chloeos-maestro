from agnes_video_batch_client import create_task, api_key, base_params

key = api_key()
try:
    p1 = base_params("landscape", seconds=4.3)
    print("Params for 4.3s:", p1)
    t1 = create_task("test prompt", key, p1)
    print("4.3s succeeded:", t1)
except Exception as e:
    print("4.3s failed:", e)

try:
    p2 = base_params("landscape", seconds=4.0)
    print("Params for 4.0s:", p2)
    t2 = create_task("test prompt", key, p2)
    print("4.0s succeeded:", t2)
except Exception as e:
    print("4.0s failed:", e)
