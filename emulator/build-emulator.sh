#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")" && pwd)"
: "${ANDROID_NDK_ROOT:?Set ANDROID_NDK_ROOT to Android NDK r30}"
: "${ANDROID_HOME:?Set ANDROID_HOME to Android SDK}"
: "${JAVA_HOME:?Set JAVA_HOME to JDK 21}"
export PATH="$JAVA_HOME/bin:$PATH"
cmake -S "$task_root/hakuX/native" -B "$task_root/hakuX/build/spikeout-android" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_ROOT/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 -DCMAKE_BUILD_TYPE=Release \
  -DNC_DEPS="$task_root/deps" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  '-DHAKUX_ARCH=armv8.2-a+fp16+dotprod+rcpc'
cmake --build "$task_root/hakuX/build/spikeout-android" --target hakuxcore -j "${BUILD_JOBS:-8}"
case "$(uname -s)" in
  Linux*) host=linux-x86_64;;
  Darwin*) host=darwin-x86_64;;
  *) echo 'Use Linux/macOS or adapt the Windows build commands from BUILD.md.' >&2; exit 1;;
esac
task_build="$task_root/hakuX/build/spikeout-android"
task_libs="$task_root/hakuX/android/app/src/main/jniLibs/arm64-v8a"
task_strip="$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/$host/bin/llvm-strip"
mkdir -p "$task_libs"
"$task_strip" -o "$task_libs/libhakuxcore.so" "$task_build/libhakuxcore.so"
"$task_strip" -o "$task_libs/libSDL3.so" "$task_build/sdl3/libSDL3.so"
for lib in main_hook file_redirect_hook gsl_alloc_hook kgsl_context_hook hook_impl; do
  "$task_strip" -o "$task_libs/lib$lib.so" "$task_build/adrenotools/src/hook/lib$lib.so"
done
cd "$task_root/hakuX/android"
sh ./gradlew :app:assembleDebug --no-daemon --console=plain \
  "-Dorg.gradle.java.home=$JAVA_HOME" \
  -Pspikeout.ndkVersion=30.0.16248370 "-Pspikeout.ndkPath=$ANDROID_NDK_ROOT"
echo 'APK: hakuX/android/app/build/outputs/apk/debug/app-debug.apk'
