# AI Practices, Transparency & Disclaimer

This document explains how **RenPy Studio** was built, the exact mobile hardware it was tested on, the role of AI in its creation, and important disclaimers for anyone using this tool.

---

## 1. Mobile-Only Development (No PC Used)

- **Zero Desktop Hardware:** The creator (**Resteus**) does **not** own a PC or laptop. Every line of Python, HTML, CSS, JavaScript, and Bash—along with all debugging, APK signing, and Git pushes—was executed 100% on a single Android smartphone inside **Termux**.
- **Creator Background:** Resteus is **not a professional developer** and started this project with **no formal software engineering experience**, building RenPy Studio through hands-on trial, real-device testing, and step-by-step AI collaboration.

### Primary Development & Test Device Specs
All builds and runtime tests for v1.0.0 were performed exclusively on:
- **Device Model:** realme RMX5020
- **OS & Architecture:** Android 16 (realme UI 7.0, `aarch64` / ARM64)
- **CPU:** MediaTek MT6769 (Octa-core @ 2.0 GHz)
- **RAM:** 8 GB
- **GPU:** Mali-G52 MC2
- **Runtime Environment:** Termux (Bash, ARM64 Python, OpenJDK 17, `apktool`, `aapt2`, `apksigner`, `zipalign`)

---

## 2. AI Contributor Introduction (Gemini Hydrogen High)

> **Hi, I'm Gemini**—specifically running as **Gemini Hydrogen High** during the engineering of RenPy Studio.
>
> **My Role in This Project:** Working alongside Resteus directly inside a mobile Termux workflow, I helped translate project goals into working code—structuring the Bottle/Waitress web server, writing the `apktool` and `apksigner` packaging pipeline, designing the mobile-first Web UI, diagnosing Android 16 / Ren'Py 8.6.1 compatibility quirks, and drafting the repository documentation.
>
> **Important Limitation:** **Gemini is an AI and can make mistakes.** AI-generated code can overlook edge cases, behave differently on other Android OEM skins or chipsets, or break when faced with unusual Ren'Py project structures. Every feature in this repo was shaped by Resteus testing real APKs on an actual phone and reporting what worked or failed.

---

## 3. Disclaimer & Limitation of Liability

- **Provided "AS-IS" Without Warranty:** RenPy Studio is an independent, community-built hobby project provided **AS-IS**, without warranties of any kind—express or implied.
- **No Liability for Device or App Issues:** Neither the creator (**Resteus**) nor **Gemini / Google** is responsible or liable if an APK packaged with this tool crashes, fails to install, exhibits display/input bugs, or causes issues on your smartphone or your players' devices.
- **User Responsibility & Backups:**
  - Always back up your original Ren'Py project files before packaging.
  - Back up your `.jks` signing keystores (`~/renpy-studio/keystores/`) in a safe offline location—if a keystore is lost, Android will not allow you to publish updates over previously installed APKs.
  - You are solely responsible for ensuring you hold the rights to any game scripts, artwork, audio, and assets you package into an APK.
