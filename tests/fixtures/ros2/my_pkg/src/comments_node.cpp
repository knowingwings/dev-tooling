#include <string>

/// Node that publishes motor state.
std::string topic_name()
{
  // TODO: make this a parameter
  return "/motor/state";  // REF(ROS 2 naming design doc): absolute names skip namespace remaps
}
