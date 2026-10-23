"""Retired schema v1 repair entry point; historical results remain unchanged."""
import argparse

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    parser.error('Legacy severity/actionability repairs are retired. Use the factual v2 runner; it retains failures without automatic repairs or retries.')

if __name__ == '__main__':
    main()
