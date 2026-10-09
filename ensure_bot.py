import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
PYW = r'C:\Users\deel\AppData\Local\Programs\Python\Python314\pythonw.exe'


def main():
    import bot
    if bot.beat_ok():
        return
    subprocess.Popen([PYW, str(BASE / 'bot.py')], cwd=str(BASE), creationflags=0x00000008)
    print('BOT_RESTARTED')


if __name__ == '__main__':
    main()
