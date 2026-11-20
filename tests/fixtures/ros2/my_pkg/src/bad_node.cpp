#include <chrono>
#include <iostream>
#include <thread>
namespace rclcpp { struct Node { template<class T> int create_publisher(const char*, int); int create_wall_timer(int, int); }; }
void spin_some(int);
struct Msg {};
void run(rclcpp::Node & node)
{
  auto pub = node.create_publisher<Msg>("cmd_vel", 10);
  auto t = node.create_wall_timer(1, 2);
  auto now = std::chrono::system_clock::now();
  std::cout << "hi";
  std::this_thread::sleep_for(std::chrono::milliseconds(10));
  spin_some(1);
  // lint-allow(ros-no-wall-timer): hardware watchdog must use wall time
  auto t2 = node.create_wall_timer(1, 2);
  // lint-allow(ros-no-wall-timer): ok
  auto t3 = node.create_wall_timer(1, 2);
  (void)pub; (void)t; (void)now; (void)t2; (void)t3;
}
