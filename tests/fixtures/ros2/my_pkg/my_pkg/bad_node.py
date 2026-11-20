import time


def tick(node):
    print('hi')
    time.sleep(0.1)
    node.create_publisher(int, 'x', 10)
    return time.time()
