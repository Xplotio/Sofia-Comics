-- SQL Script para la creación de la base de datos SofiaComics

-- Eliminar la base de datos si ya existe (¡CUIDADO! Esto borrará todos los datos existentes)
DROP DATABASE IF EXISTS SofiaComics;

-- Crear la base de datos
CREATE DATABASE SofiaComics;

-- Usar la base de datos recién creada
USE SofiaComics;

-- Tabla Editorial
CREATE TABLE Editorial (
    id_editorial INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Tabla Usuario
CREATE TABLE Usuario (
    correo_usuario VARCHAR(255) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    contraseña VARCHAR(255) NOT NULL, -- Almacenar contraseñas hasheadas
    fecha_creacion DATE NOT NULL
);

-- Tabla Usuario_editorial (para usuarios que gestionan editoriales)
CREATE TABLE Usuario_editorial (
    correo_editorial VARCHAR(255) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    contraseña VARCHAR(255) NOT NULL, -- Almacenar contraseñas hasheadas
    id_editorial INT NOT NULL,
    FOREIGN KEY (id_editorial) REFERENCES Editorial(id_editorial)
);

-- Tabla Personaje
CREATE TABLE Personaje (
    id_personaje INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    imagen LONGBLOB, -- Para almacenar la imagen del personaje
    id_editorial INT,
    FOREIGN KEY (id_editorial) REFERENCES Editorial(id_editorial)
);

-- Tabla Comic
CREATE TABLE Comic (
    codigo_de_barras INT PRIMARY KEY, -- Usado como ID único del cómic
    titulo VARCHAR(255) NOT NULL,
    autor VARCHAR(100),
    descripcion TEXT,
    id_editorial INT NOT NULL,
    fecha_publicacion DATE,
    portada LONGBLOB, -- Para almacenar la imagen de la portada
    contenido LONGBLOB, -- Para almacenar el PDF del cómic
    FOREIGN KEY (id_editorial) REFERENCES Editorial(id_editorial)
);

-- Tabla ComicPersonaje (Tabla de relación muchos a muchos entre Comic y Personaje)
CREATE TABLE ComicPersonaje (
    codigo_de_barras INT NOT NULL,
    id_personaje INT NOT NULL,
    PRIMARY KEY (codigo_de_barras, id_personaje),
    FOREIGN KEY (codigo_de_barras) REFERENCES Comic(codigo_de_barras) ON DELETE CASCADE,
    FOREIGN KEY (id_personaje) REFERENCES Personaje(id_personaje) ON DELETE CASCADE
);

-- Tabla Preferencias_usuario
CREATE TABLE Preferencias_usuario (
    correo_usuario VARCHAR(255) NOT NULL,
    id_personaje INT NOT NULL,
    fecha_agregado DATE NOT NULL,
    PRIMARY KEY (correo_usuario, id_personaje),
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario) ON DELETE CASCADE,
    FOREIGN KEY (id_personaje) REFERENCES Personaje(id_personaje) ON DELETE CASCADE
);

-- Tabla Calificaciones (para las calificaciones de los cómics)
CREATE TABLE Calificaciones (
    correo_usuario VARCHAR(255) NOT NULL,
    codigo_de_barras INT NOT NULL,
    calificacion INT CHECK (calificacion >= 1 AND calificacion <= 5) NOT NULL,
    fecha_calificacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (correo_usuario, codigo_de_barras),
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario) ON DELETE CASCADE,
    FOREIGN KEY (codigo_de_barras) REFERENCES Comic(codigo_de_barras) ON DELETE CASCADE
);

-- Tabla HistorialLectura
CREATE TABLE HistorialLectura (
    id_lectura INT AUTO_INCREMENT PRIMARY KEY,
    correo_usuario VARCHAR(255) NOT NULL,
    codigo_de_barras INT NOT NULL,
    fecha_lectura DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario) ON DELETE CASCADE,
    FOREIGN KEY (codigo_de_barras) REFERENCES Comic(codigo_de_barras) ON DELETE CASCADE
);

-- Tabla Planes_suscripcion
CREATE TABLE Planes_suscripcion (
    id_plan INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    costo_suscripcion DECIMAL(10, 2) NOT NULL,
    duracion_meses INT NOT NULL
);

-- Tabla Suscripciones
CREATE TABLE Suscripciones (
    id_suscripcion INT AUTO_INCREMENT PRIMARY KEY,
    correo_usuario VARCHAR(255) NOT NULL UNIQUE, -- Un usuario solo tiene una suscripción activa a la vez
    id_plan INT NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    estado ENUM('Activa', 'Inactiva', 'Pendiente', 'Cancelada') NOT NULL,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario) ON DELETE CASCADE,
    FOREIGN KEY (id_plan) REFERENCES Planes_suscripcion(id_plan)
);

-- Tabla Transacciones
CREATE TABLE Transacciones (
    id_transaccion INT AUTO_INCREMENT PRIMARY KEY,
    correo_usuario VARCHAR(255) NOT NULL,
    id_plan INT NOT NULL,
    cantidad DECIMAL(10, 2) NOT NULL,
    fecha_transaccion DATETIME DEFAULT CURRENT_TIMESTAMP,
    metodo_pago VARCHAR(50),
    referencia VARCHAR(255) UNIQUE,
    estado ENUM('Pendiente', 'Completada', 'Fallida', 'Reembolsada') NOT NULL,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario) ON DELETE CASCADE,
    FOREIGN KEY (id_plan) REFERENCES Planes_suscripcion(id_plan)
);


-- Inserción de datos iniciales (Opcional, pero recomendado para pruebas)

-- Editoriales
INSERT INTO Editorial (nombre) VALUES
('Marvel Comics'),
('DC Comics'),
('Image Comics'),
('Dark Horse Comics');

-- Planes de Suscripción (Asegúrate de que 'Premium' existe para la lógica de suscripción)
INSERT INTO Planes_suscripcion (nombre, costo_suscripcion, duracion_meses) VALUES
('Mensual', 5.99, 1),
('Anual', 59.99, 12),
('Premium', 99.99, 12);

-- Usuario de ejemplo (contraseña 'password123' hasheada con SHA256)
-- Puedes generar el hash de 'password123' con: SELECT SHA2('password123', 256);
-- El hash para 'password123' es: 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27a83'
INSERT INTO Usuario (correo_usuario, nombre, contraseña, fecha_creacion) VALUES
('usuario@example.com', 'Usuario Ejemplo', 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27a83', CURDATE()),
('xplotiolas@gmail.com', 'Xplotiolas', 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27a83', CURDATE());

-- Usuario editorial de ejemplo (contraseña 'editorial123' hasheada)
-- Hash para 'editorial123': '59e1966028823f666f294025d2334f552f954e7d4d4455850e04622081d64344'
INSERT INTO Usuario_editorial (correo_editorial, nombre, contraseña, id_editorial) VALUES
('marvel_editor@example.com', 'Editor Marvel', '59e1966028823f666f294025d2334f552f954e7d4d4455850e04622081d64344', (SELECT id_editorial FROM Editorial WHERE nombre = 'Marvel Comics')),
('dc_editor@example.com', 'Editor DC', '59e1966028823f666f294025d2334f552f954e7d4d4455850e04622081d64344', (SELECT id_editorial FROM Editorial WHERE nombre = 'DC Comics'));

-- Cómics de ejemplo (sin contenido BLOB, solo para estructura)
INSERT INTO Comic (codigo_de_barras, titulo, autor, descripcion, id_editorial, fecha_publicacion) VALUES
(1001, 'Amazing Spider-Man #1', 'Stan Lee', 'El debut de Spider-Man.', (SELECT id_editorial FROM Editorial WHERE nombre = 'Marvel Comics'), '1963-03-01'),
(1002, 'Batman: Year One', 'Frank Miller', 'El origen moderno de Batman.', (SELECT id_editorial FROM Editorial WHERE nombre = 'DC Comics'), '1987-02-01'),
(1003, 'The Walking Dead #1', 'Robert Kirkman', 'El inicio del apocalipsis zombie.', (SELECT id_editorial FROM Editorial WHERE nombre = 'Image Comics'), '2003-10-08');

-- Personajes de ejemplo (sin imagen BLOB, solo para estructura)
INSERT INTO Personaje (nombre, descripcion, id_editorial) VALUES
('Spider-Man', 'Un héroe arácnido de Nueva York.', (SELECT id_editorial FROM Editorial WHERE nombre = 'Marvel Comics')),
('Batman', 'El Caballero Oscuro de Gotham.', (SELECT id_editorial FROM Editorial WHERE nombre = 'DC Comics')),
('Rick Grimes', 'Líder de supervivientes en un mundo post-apocalíptico.', (SELECT id_editorial FROM Editorial WHERE nombre = 'Image Comics'));

-- Relaciones Comic-Personaje de ejemplo
INSERT INTO ComicPersonaje (codigo_de_barras, id_personaje) VALUES
(1001, (SELECT id_personaje FROM Personaje WHERE nombre = 'Spider-Man')),
(1002, (SELECT id_personaje FROM Personaje WHERE nombre = 'Batman'));

-- Suscripción de ejemplo para xplotiolas@gmail.com (Premium)
-- La contraseña de xplotiolas@gmail.com es 'password123'
-- La suscripción se establecerá como 'Activa' por 12 meses (asumiendo id_plan 3 para Premium)
INSERT INTO Suscripciones (correo_usuario, id_plan, fecha_inicio, fecha_fin, estado)
VALUES (
    'xplotiolas@gmail.com',
    (SELECT id_plan FROM Planes_suscripcion WHERE nombre = 'Premium'),
    CURDATE(),
    DATE_ADD(CURDATE(), INTERVAL 12 MONTH),
    'Activa'
);

