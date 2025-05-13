# MIDI Genre Generator

The MIDI Genre Generator is a tool for creating MIDI files in various musical styles and genres. It allows users to select styles, substyles, instruments, and other musical parameters to generate MIDI compositions.

## Features

- Generate MIDI files in different genres and substyles.
- Customize instruments, BPM, key, and mode.
- Live MIDI mode for real-time composition.

## Requirements

- Python 3.10 or higher
- Virtual environment setup
- Required Python packages (see `requirements.txt`)

## Setup

### Windows

Run the `setup_environment.bat` script:

```cmd
setup_environment.bat
```

### Linux/MacOS

Run the `setup_environment.sh` script:

```bash
bash setup_environment.sh
```

## Usage

1. Activate the virtual environment:

   - Windows: `\path\to\.venv\Scripts\activate.bat`
   - Linux/MacOS: `source .venv/bin/activate`

2. Run the MIDI generator script:

```bash
python src/midi_generator.py
```

## Troubleshooting

- Check the `midi_generator.log` file for detailed logs and error messages.
- Ensure all dependencies are installed correctly.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
