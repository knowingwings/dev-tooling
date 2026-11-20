# include(cmake/warnings.cmake) then call fw_strict_warnings(<target>) on YOUR targets only.
# Don't apply to vendor HAL / CMSIS / RTOS targets: they won't survive these flags.

function(fw_strict_warnings target)
  target_compile_options(${target} PRIVATE
    -Wall -Wextra -Werror
    -Wshadow
    -Wconversion -Wsign-conversion       # implicit narrowing: classic sensor/ADC scaling bugs
    -Wdouble-promotion                   # float silently promoted to (soft-float) double
    -Wformat=2 -Wformat-truncation=2
    -Wundef                              # #if ON_TYPO is an error, not silently 0
    -Wcast-align -Wcast-qual
    -Wnull-dereference
    -Wimplicit-fallthrough
    -Wvla                                # no variable-length arrays on a small stack
    -Wpointer-arith
    -Wswitch-enum
    -Wstack-usage=1024                   # tune to your task stack sizes
    -fstack-usage                        # writes .su files: per-function stack use
    -fno-common
    $<$<COMPILE_LANGUAGE:C>:-Wstrict-prototypes -Wmissing-prototypes -Wold-style-definition>
  )
  if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
    target_compile_options(${target} PRIVATE
      -Wlogical-op -Wduplicated-cond -Wduplicated-branches
    )
  endif()
endfunction()

# Also export compile_commands.json for clang-tidy and clangd:
#   set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
#
# Map file + size report, so an agent can see what its change cost in flash/RAM:
#   target_link_options(app PRIVATE -Wl,-Map=$<TARGET_FILE_DIR:app>/app.map -Wl,--print-memory-usage)
