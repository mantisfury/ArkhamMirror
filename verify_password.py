import bcrypt

# Hash from config
stored_hash = "$2b$12$Y3/S0Vl8u5eYzfmNd9hy0.JzsmiHlNk4W63lRxMbfXFnQhFsezcoq"

# Test passwords
test_passwords = ["admin", "password", "arkham", "Admin"]

for pwd in test_passwords:
    matches = bcrypt.checkpw(pwd.encode(), stored_hash.encode())
    print(f"Password '{pwd}': {matches}")

# Generate new hash for 'admin'
print("\nGenerating new hash for 'admin':")
new_hash = bcrypt.hashpw(b'admin', bcrypt.gensalt())
print(new_hash.decode())
