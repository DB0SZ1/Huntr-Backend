"""
MongoDB URL Password Encoder
Fixes special characters in MongoDB passwords
"""
from urllib.parse import quote_plus

print("\n" + "="*60)
print(" MONGODB URL PASSWORD ENCODER")
print("="*60 + "\n")

# Your current password with special characters
original_password = "DB0SZa2008?!"

# URL-encode the password
encoded_password = quote_plus(original_password)

print(f"Original password: {original_password}")
print(f"Encoded password:  {encoded_password}")

# Show the full URL comparison
original_url = "mongodb+srv://db0szempire:DB0SZa2008?!@cluster0.wjuw13v.mongodb.net/"
correct_url = f"mongodb+srv://db0szempire:{encoded_password}@cluster0.wjuw13v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

print("\n" + "-"*60)
print("INCORRECT URL (causes errors):")
print("-"*60)
print(original_url)

print("\n" + "-"*60)
print("CORRECT URL (use this in .env):")
print("-"*60)
print(correct_url)

print("\n" + "="*60)
print("Copy the CORRECT URL above to your .env file:")
print("="*60)
print(f"\nMONGODB_URL={correct_url}\n")

# Interactive encoder
print("\n" + "="*60)
print("Or encode a different password:")
print("="*60)
try:
    custom_password = input("\nEnter your MongoDB password (or press Enter to skip): ").strip()
    if custom_password:
        encoded_custom = quote_plus(custom_password)
        print(f"\nEncoded: {encoded_custom}")
        print(f"\nFull URL:")
        print(f"mongodb+srv://db0szempire:{encoded_custom}@cluster0.wjuw13v.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
except KeyboardInterrupt:
    print("\n\nSkipped.")

print("\n")