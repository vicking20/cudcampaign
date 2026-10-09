# Cross-compile KisakCOD (MSVC-style) for 32-bit Windows from Linux with clang-cl + xwin SDK.
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_VERSION 10.0)
set(CMAKE_SYSTEM_PROCESSOR x86)

set(CMAKE_C_COMPILER clang-cl)
set(CMAKE_CXX_COMPILER clang-cl)
set(CMAKE_LINKER lld-link)
set(CMAKE_AR llvm-lib)
set(CMAKE_RC_COMPILER llvm-rc)
set(CMAKE_MT "")

if(DEFINED ENV{XWIN_DIR})
  set(XWIN $ENV{XWIN_DIR})
else()
  set(XWIN $ENV{HOME}/cudcampaign/winsdk/sdk)
endif()

set(_flags "--target=i686-pc-windows-msvc -fms-compatibility -fms-extensions -Wno-everything \
 /imsvc ${XWIN}/crt/include /imsvc ${XWIN}/sdk/include/ucrt /imsvc ${XWIN}/sdk/include/um /imsvc ${XWIN}/sdk/include/shared")
set(CMAKE_C_FLAGS_INIT "${_flags}")
set(CMAKE_CXX_FLAGS_INIT "${_flags}")

set(_lflags "/libpath:${XWIN}/crt/lib/x86 /libpath:${XWIN}/sdk/lib/um/x86 /libpath:${XWIN}/sdk/lib/ucrt/x86")
set(CMAKE_EXE_LINKER_FLAGS_INIT "${_lflags}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_lflags}")
set(CMAKE_MODULE_LINKER_FLAGS_INIT "${_lflags}")

set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
