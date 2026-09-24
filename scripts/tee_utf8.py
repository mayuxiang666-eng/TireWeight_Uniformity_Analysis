import sys
import io
import os

def main():
    log_path = sys.argv[1]
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    stdin_wrapped = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
    stdout_wrapped = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    with open(log_path, 'a', encoding='utf-8-sig') as log:
        for line in stdin_wrapped:
            stdout_wrapped.write(line)
            stdout_wrapped.flush()
            log.write(line)
            log.flush()

if __name__ == '__main__':
    main()
