-- Elimina la base de datos si ya existe para empezar desde cero
DROP DATABASE IF EXISTS SofiaComics;

-- Crea la nueva base de datos
CREATE DATABASE SofiaComics;

-- Selecciona la base de datos para usarla
USE SofiaComics;

-- TABLAS PRINCIPALES

CREATE TABLE Usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(255) NOT NULL UNIQUE,
    contraseña TEXT NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Personajes (
    id_personaje INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT
);

CREATE TABLE Editoriales (
    id_editorial INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    pais VARCHAR(50),
    acuerdo_licencia TEXT,
    fecha_inicio_licencia DATE,
    fecha_fin_licencia DATE -- Corregido el nombre del campo
);

CREATE TABLE PlanesSuscripcion (
    id_plan INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL, -- Usar DECIMAL para precios es más preciso
    duracion_meses INT NOT NULL
);

CREATE TABLE Comics (
    id_comic INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(100) NOT NULL,
    autor VARCHAR(100),
    descripcion TEXT,
    id_editorial INT,
    fecha_publicacion DATE,
    ruta_portada VARCHAR(255), -- Campo para la imagen de portada
    FOREIGN KEY (id_editorial) REFERENCES Editoriales(id_editorial)
);

-- TABLAS DE RELACIÓN (MUCHOS A MUCHOS)

CREATE TABLE PreferenciasUsuario (
    id_preferencia INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT,
    id_personaje INT,
    fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
    FOREIGN KEY (id_personaje) REFERENCES Personajes(id_personaje)
);

CREATE TABLE Calificaciones (
    id_calificacion INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT,
    id_comic INT,
    calificacion INT,
    comentario TEXT,
    fecha_calificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
    FOREIGN KEY (id_comic) REFERENCES Comics(id_comic),
    CHECK (calificacion >= 1 AND calificacion <= 5) -- Asegura que la calificación esté entre 1 y 5
);

CREATE TABLE Suscripciones (
    id_suscripcion INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT,
    id_plan INT,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    estado VARCHAR(50), -- 'activa', 'cancelada', 'expirada'
    FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
    FOREIGN KEY (id_plan) REFERENCES PlanesSuscripcion(id_plan)
);

CREATE TABLE Transacciones (
    id_transaccion INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT,
    id_suscripcion INT, -- Es mejor ligar la transacción a una suscripción específica
    cantidad DECIMAL(10, 2) NOT NULL,
    fecha_transaccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metodo_pago VARCHAR(50),
    referencia_pago VARCHAR(255),
    estado VARCHAR(50), -- 'completada', 'fallida', 'pendiente'
    FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
    FOREIGN KEY (id_suscripcion) REFERENCES Suscripciones(id_suscripcion)
);

-- ¡NUEVA TABLA PARA REGISTRAR LECTURAS!
CREATE TABLE HistorialLectura (
    id_historial INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT,
    id_comic INT,
    fecha_lectura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
    FOREIGN KEY (id_comic) REFERENCES Comics(id_comic)
);

-- Nota: La tabla Usuario_editorial parecía duplicar la información de un usuario.
-- Si la intención es tener usuarios con rol de "editor", se podría manejar con un campo de "rol" en la tabla Usuarios.
-- Por ahora, la he omitido para simplificar el esquema. Si es necesaria, la podemos añadir de nuevo.
ALTER TABLE Comics
ADD COLUMN pdf_path VARCHAR(255);

-- Crea la tabla Comic_Personaje para la relación muchos a muchos
-- entre Comics y Personajes
CREATE TABLE IF NOT EXISTS Comic_Personaje (
    id_comic_personaje INT AUTO_INCREMENT PRIMARY KEY,
    id_comic INT,
    id_personaje INT,
    FOREIGN KEY (id_comic) REFERENCES Comics(id_comic),
    FOREIGN KEY (id_personaje) REFERENCES Personajes(id_personaje),
    UNIQUE (id_comic, id_personaje) -- Evita duplicados para la misma combinación cómic-personaje
);

