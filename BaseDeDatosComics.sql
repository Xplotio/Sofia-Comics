create table Usuario (
id_usuario int primary key,
nombre varchar(100),
correo text,
contraseña text,
fecha_creacion date
);

create table Personaje (
id_personaje int primary key,
nombre varchar(100),
descripcion text
);

create table editorial (
id_editorial int primary key,
nombre varchar(100),
pais varchar(50),
acuerdo_licencia text,
fecha_inicio_licencia date,
fecha_fecha_licencia date,
precio int
);

create table Usuario_editorial (
id_usuario_editorial int primary key,
nombre varchar(100),
correo text,
contraseña text,
fecha_creacion date,
id_editorial int,
FOREIGN KEY (id_editorial) REFERENCES Usuarios(id_editorial)
);

create table Comic (
id_comic int primary key,
titulo varchar(100),
autor varchar(100),
descripcion text,
id_editorial int,
fecha_publicacion date,
FOREIGN KEY (id_editorial) REFERENCES Usuarios(id_editorial)
);

create table Preferencias_usuario (
id_preferencia int primary key,
id_usuario int,
id_personaje int,
fecha_agregado date,
FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
FOREIGN KEY (id_personaje) REFERENCES Usuarios(id_personaje)
);

create table Calificaciones (
id_calificacion int primary key,
id_usuario int,
id_comic int,
calificacion integer(5),
FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
FOREIGN KEY (id_comic) REFERENCES Usuarios(id_comic)
);

create table Planes_suscripcion (
id_plan int primary key,
nombre varchar(100),
precio int,
duracion_meses int
);

create table Suscripciones (
id_suscripcion int primary key,
id_usuario int,
id_plan int,
fecha_inicio date,
fecha_fin date,
estado text,
FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
FOREIGN KEY (id_plan) REFERENCES Usuarios(id_plan)
);

create table Transacciones (
id_transaccion int primary key,
id_usuario int,
id_plan int,
cantidad int,
fecha_transaccion date,
metodo_pago text,
referencia text,
estado text,
FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
FOREIGN KEY (id_plan) REFERENCES Usuarios(id_plan)
);