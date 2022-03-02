#!/usr/bin/env python3
import wa


def main():
    wa.run()


def lambda_event(*args, **kwargs):
    main()


if __name__ == "__main__":
    main()
