# Corresponding source: hakuX Spikeout KR v0.8

This source archive accompanies `hakuX-Spikeout-KR-1.3.0-v0.8.apk`.
The modified application is based on hakuX v1.3.0, commit
`a90f01ee4629977b36a76175cbd781d383056293`, under GPL-3.0-or-later.
See `hakuX/COPYING`, `hakuX/LICENSE`, `hakuX/licenses/`, and the dependencies'
own license files. All these sources retain their original authorship.

The archive includes the modified hakuX tree, its populated FEX fork and
the native dependencies actually used by this build. The supplied diff and
`provenance.json` describe our changes. `source-files-sha256.json` records
the archived source files. No game image, Xbox BIOS, MCPX ROM, private
signing key or device save data is required or included.

## Build on Linux

Install CMake, Ninja, Python 3, JDK 21, Android SDK platform 36 / build tools
36.1.0, and Android NDK r30 (30.0.16248370). Set `ANDROID_HOME`,
`ANDROID_NDK_ROOT` and `JAVA_HOME`, then run `bash build-emulator.sh` from
this archive's top directory. SDK licenses must be accepted by the builder.
The included Gradle wrapper downloads the Android/Kotlin dependencies.

The native CPU target is `armv8.2-a+fp16+dotprod+rcpc`, arm64-v8a,
minimum Android API 28. The app target SDK is 36. This is the target used
by the tested Adreno 740 device, not a promise of support for every ARM64 GPU.

## Windows build used for the distributed binary

Use the same CMake arguments with NDK r30's Windows toolchain and Ninja.
Build `hakuxcore` in `hakuX/build/spikeout-android`, then strip and copy
`libhakuxcore.so`, `sdl3/libSDL3.so`, and the five adrenotools hook libraries
listed in `build-emulator.sh` into
`hakuX/android/app/src/main/jniLibs/arm64-v8a`.

From `hakuX/android`, run `gradlew.bat :app:assembleDebug --no-daemon`
with `-Dorg.gradle.java.home=<JDK21>` and
`-Pspikeout.ndkVersion=30.0.16248370 -Pspikeout.ndkPath=<NDKr30>`.
The Java home argument overrides an upstream machine-specific Gradle setting.
Git for Windows' `gzip` and a `python3` command may be needed by FEX's generators.

The distributed APK uses a local Android debug certificate. It was built with
JDK 21.0.13+9 and the toolchain versions recorded in `provenance.json`.
Building locally creates your own signing certificate; byte-identical APK
hashes and update compatibility with our signed APK are not promised.

## Mesa driver

`hakuX/android/app/src/main/assets/spikeout/Turnip_v26.0.0_R8.zip` is an
unmodified package from K11MCH1's v26.0.0-rc08 release. Its SHA-256 is
`e634db0f929e2205e95511c769071817d0390180ec72c8e690bc76375e813715`.
The bundled binary package is separate from the GPL hakuX core; Mesa
retains its own MIT and file-specific licenses. License information and
upstream copyright notices are provided alongside this source package.

The release's initial-driver installation was compiled and its asset checked.
The new bootstrap and v0.8 subtitle outline still require on-device visual
verification; the native core and driver match the previously tested binaries.
