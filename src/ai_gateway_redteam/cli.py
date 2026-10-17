import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="aigw-redteam")
    parser.add_argument("cases", help="YAML file or folder of attack cases")
    args = parser.parse_args()
    print(f"would run cases from: {args.cases}")


if __name__ == "__main__":
    main()
