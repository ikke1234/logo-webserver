from app import auth

def main():
    print("Admin gebruiker aanmaken")
    username = input("Gebruikersnaam: ").strip()
    password = input("Wachtwoord: ").strip()
    auth.create_user(username, password, "admin")
    print(f"Gebruiker '{username}' met rol 'admin' aangemaakt.")

if __name__ == "__main__":
    main()
