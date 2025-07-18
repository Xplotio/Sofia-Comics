-- Script SQL corregido para la base de datos SofiaComics

-- Eliminar la base de datos si existe para empezar desde cero
DROP DATABASE IF EXISTS SofiaComics;

-- Crear la base de datos
CREATE DATABASE SofiaComics;

-- Usar la base de datos
USE SofiaComics;

-- Tabla Usuario
CREATE TABLE Usuario (
    correo_usuario VARCHAR(255) PRIMARY KEY, -- Corregido: VARCHAR con longitud para PRIMARY KEY
    nombre VARCHAR(100),
    contraseña TEXT,
    fecha_creacion DATE
);

-- Tabla Personaje
CREATE TABLE Personaje (
    id_personaje INT PRIMARY KEY,
    nombre VARCHAR(100),
    descripcion TEXT,
    imagen LONGBLOB -- Se mantiene LONGBLOB para almacenar el archivo binario
);

-- Tabla Editorial
CREATE TABLE Editorial (
    id_editorial INT PRIMARY KEY,
    nombre VARCHAR(100),
    fecha_inicio_licencia DATE,
    fecha_fin_licencia DATE,
    costo_licencia FLOAT
);

-- Tabla Planes_suscripcion
CREATE TABLE Planes_suscripcion (
    id_plan INT PRIMARY KEY,
    nombre VARCHAR(100),
    costo_suscripcion FLOAT,
    duracion_meses INT
);

-- Tabla Usuario_editorial
CREATE TABLE Usuario_editorial (
    nombre VARCHAR(100),
    correo_editorial VARCHAR(255) PRIMARY KEY, -- Corregido: VARCHAR con longitud para PRIMARY KEY
    contraseña TEXT,
    fecha_creacion DATE,
    id_editorial INT,
    FOREIGN KEY (id_editorial) REFERENCES Editorial(id_editorial)
);

-- Tabla Comic
CREATE TABLE Comic (
    codigo_de_barras INT PRIMARY KEY,
    titulo VARCHAR(100),
    autor VARCHAR(100),
    descripcion TEXT,
    id_editorial INT,
    fecha_publicacion DATE,
    portada LONGBLOB, -- Se mantiene LONGBLOB
    contenido LONGBLOB, -- Se mantiene LONGBLOB
    FOREIGN KEY (id_editorial) REFERENCES Editorial(id_editorial)
);

-- Tabla Preferencias_usuario
CREATE TABLE Preferencias_usuario (
    id_preferencia INT PRIMARY KEY AUTO_INCREMENT,
    correo_usuario VARCHAR(255), -- Corregido: VARCHAR con longitud para FOREIGN KEY
    id_personaje INT,
    fecha_agregado DATE,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario),
    FOREIGN KEY (id_personaje) REFERENCES Personaje(id_personaje)
);

-- Tabla Calificaciones
CREATE TABLE Calificaciones (
    id_calificacion INT PRIMARY KEY,
    correo_usuario VARCHAR(255), -- Corregido: VARCHAR con longitud para FOREIGN KEY
    codigo_de_barras INT,
    calificacion INTEGER,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario),
    FOREIGN KEY (codigo_de_barras) REFERENCES Comic(codigo_de_barras),
    CONSTRAINT CHK_Calificacion CHECK (calificacion >= 1 AND calificacion <= 5)
);

-- Tabla Suscripciones
CREATE TABLE Suscripciones (
    id_suscripcion INT PRIMARY KEY,
    correo_usuario VARCHAR(255), -- Corregido: VARCHAR con longitud para FOREIGN KEY
    id_plan INT,
    fecha_inicio DATE,
    fecha_fin DATE,
    estado TEXT,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario),
    FOREIGN KEY (id_plan) REFERENCES Planes_suscripcion(id_plan)
);

-- Tabla Transacciones
CREATE TABLE Transacciones (
    id_transaccion INT PRIMARY KEY,
    correo_usuario VARCHAR(255), -- Corregido: VARCHAR con longitud para FOREIGN KEY
    id_plan INT,
    cantidad INT,
    fecha_transaccion DATE,
    metodo_pago TEXT,
    referencia TEXT,
    estado TEXT,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario),
    FOREIGN KEY (id_plan) REFERENCES Planes_suscripcion(id_plan)
);

-- Tabla HistorialLectura
CREATE TABLE HistorialLectura (
    id_historial INT AUTO_INCREMENT PRIMARY KEY,
    correo_usuario VARCHAR(255), -- Corregido: VARCHAR con longitud para FOREIGN KEY
    codigo_de_barras INT,
    fecha_lectura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (correo_usuario) REFERENCES Usuario(correo_usuario),
    FOREIGN KEY (codigo_de_barras) REFERENCES Comic(codigo_de_barras)
);

-- Tabla ComicPersonaje (Tabla de unión para relación muchos a muchos)
CREATE TABLE ComicPersonaje (
    id_comic_personaje INT AUTO_INCREMENT PRIMARY KEY,
    codigo_de_barras INT,
    id_personaje INT,
    FOREIGN KEY (codigo_de_barras) REFERENCES Comic(codigo_de_barras),
    FOREIGN KEY (id_personaje) REFERENCES Personaje(id_personaje)
);
