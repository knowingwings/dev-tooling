# --- Paste into each ament_cmake package's CMakeLists.txt ---------------------

# Strict warnings on your own targets. -Werror turns "the agent ignored a warning" into a failed build.
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(
    -Wall -Wextra -Wpedantic -Werror
    -Wshadow -Wconversion -Wsign-conversion
    -Wnon-virtual-dtor -Woverloaded-virtual -Wold-style-cast
    -Wnull-dereference -Wimplicit-fallthrough
  )
endif()

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # clang-format, clang-tidy, ruff and check_patterns.py replace these (and disagree with some of them):
  list(APPEND AMENT_LINT_AUTO_EXCLUDE
    ament_cmake_uncrustify
    ament_cmake_cpplint
    ament_cmake_flake8
    ament_cmake_pep257
  )
  # Still useful: cppcheck, xmllint (package.xml), lint_cmake, copyright.
  ament_lint_auto_find_test_dependencies()
endif()

# --- ~/.colcon/defaults.yaml (once per machine) -------------------------------
# Makes every colcon build emit compile_commands.json for clang-tidy and clangd:
#
# build:
#   cmake-args:
#     - -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
#   symlink-install: true
