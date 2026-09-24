# Replacing the LGPL Qt Libraries

The distributed Windows executable uses the unmodified Qt and PySide6 6.8.3 libraries from the official Qt for Python wheels. The application source code and reproducible build command are provided so recipients can inspect, replace, and rebuild against a compatible modified Qt/PySide6 distribution.

1. Install Python 3.12 and create a clean virtual environment.
2. Install a compatible PySide6 distribution. To test a modified LGPL build, install that wheel in place of the PyPI `PySide6==6.8.3` wheel.
3. Install `pyinstaller==6.22.3`.
4. Run the single-file build command documented in `README.md`.

The application does not perform integrity checks on Qt libraries and does not prohibit reverse engineering needed to debug changes to LGPL-covered components. The full LGPLv3 text and corresponding upstream source location are provided with every release.
