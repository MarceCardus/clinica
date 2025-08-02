def aumentar_version():
    with open('version.txt', 'r+') as f:
        linea = f.readline().strip()
        if not linea:
            print("El archivo version.txt está vacío. Escriba una versión inicial, por ejemplo: 1.0.0")
            return
        partes = linea.split('.')
        if not all(p.isdigit() for p in partes):
            print("La versión tiene un formato inválido. Debe ser como: 1.0.0")
            return
        partes[-1] = str(int(partes[-1]) + 1)
        nueva_version = '.'.join(partes)
        f.seek(0)
        f.write(nueva_version)
        f.truncate()
    print(f"Nueva versión: {nueva_version}")

if __name__ == "__main__":
    aumentar_version()
