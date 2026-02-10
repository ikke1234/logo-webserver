from app import auth

def main():
    print("Gebruiker aanmaken")
    username = input("Gebruikersnaam: ").strip()
    password = input("Wachtwoord: ").strip()
    role = input("Rol (viewer/editor/admin): ").strip().lower()
    auth.create_user(username, password, role)
    print("Klaar.")

if __name__ == "__main__":
    main()
