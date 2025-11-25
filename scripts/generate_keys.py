import yaml
import streamlit_authenticator as stauth

# This script generates a hashed password for use in config.yaml


def generate_hash():
    print("ArkhamMirror Password Hasher")
    print("----------------------------")
    password = input("Enter the password you want to use: ")

    # stauth.Hasher was the old way, newer versions use Hasher([passwords]).generate()
    # Let's try to be compatible with common versions
    try:
        hashed_passwords = stauth.Hasher([password]).generate()
        hashed_password = hashed_passwords[0]
        print(
            "\nSUCCESS! Copy this string into your config.yaml under credentials -> usernames -> admin -> password:"
        )
        print(f"\n{hashed_password}\n")
    except Exception as e:
        print(f"Error generating hash: {e}")


if __name__ == "__main__":
    generate_hash()
