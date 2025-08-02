import sys

nueva_version = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
with open("version.txt", "w") as f:
    f.write(nueva_version)
print(f"Versión actualizada a {nueva_version}")
