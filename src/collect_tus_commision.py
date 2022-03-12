



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--encrypt", action="store_true")
    group.add_argument("--decrypt", action="store_true")
    options = parser.parse_args()

    key_str = getpass.getpass(prompt="Enter decryption password: ")
    byte_key = str.encode(key_str)
    data_str = input("Enter data to encrypt/decrypt: ")
    if options.encrypt:
        output = encrypt(byte_key, str.encode(data_str), encode=True)
    else:
        output = decrypt(byte_key, data_str, decode=True).decode()
    print(output)
