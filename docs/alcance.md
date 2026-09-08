# Alcance

Futbot es un juego competitivo que une fútbol y programación, enfrentando a diferentes usuarios en partidos uno contra uno. Cada enfrentamiento se compone de jugadores-bots compitiendo de forma autónoma a partir de diferentes comportamientos definidos previamente por el usuario. Este último, durante el transcurso del partido actuará a modo de “director técnico” intercambiando en tiempo real el comportamiento elegido de cada uno de sus jugadores-bot y sustituyendo jugadores. 

El fin de un usuario en cada partido es vencer al usuario oponente superándolo en goles al concluir el partido. Esto se logra influyendo estratégicamente en sus jugadores-bot para anotar más goles que su contrincante.

Futbot desafía a cada usuario a tener su propio club, el cual podrá administrar de diferentes formas, personalizando su nombre y escudo, sus jugadores y tácticas (comportamientos) y preparando una plantilla para futuros partidos. 
En relación a los jugadores-bot, el usuario podrá crearlos y personalizarlos mediante dos sistemas: 

Un sistema estático PACS, el cuál representará los atributos deportivos de cada jugador-bot.
Un sistema dinámico de Comportamientos, los cuales representan el estilo de juego que tendrá cada jugador-bot en cada momento del partido. Estos comportamientos serán elegidos e intercambiados por el usuario-jugador en su rol de director técnico de forma manual durante el partido. Cada comportamiento será definido por el usuario mediante una interfaz preestablecida de primitivas que son código de Python.

Futbot ofrece dos modos de juego: los usuarios podrán crear ligas para competir contra otros usuarios, jugando cada usuario un partido contra cada usuario diferente de él y disputando así una tabla de posiciones de la Liga. Por otro lado,  los usuarios podrán jugar partidos amistosos contra otro usuario.
Un partido vivo cuenta con cuatro períodos (divididos por dos pausas de hidratación y un entre-tiempo) y el tiempo total de un partido podrá ser definido por el usuario que crea la liga o el partido amistoso. Durante un partido un usuario-jugador conectado de manera sincrónica puede cambiar en los comportamientos de sus jugadores-bots para intentar favorecer para sí mismo el resultado final del partido mismo. El usuario jugador, quien previamente definió tres jugadores principales y tres jugadores-bot suplentes, puede a su vez realizar cambios de jugadores, específicamente uno por tiempo.
Todos los partidos de liga como amistosos que sean públicos generarán estadísticas tanto a nivel de cada club como globales para poder comparar entre todos los usuarios.


## Características principales:

### Usuario/club:

- Los jugadores de FutBot pueden registrarse como usuarios, teniendo solo un club asociado con su respectivo nombre y avatar como escudo. Ambos campos son elegidos y cargados por el usuario. 
- El usuario está ligado al club y se proveerá método de autenticación al iniciar sesión y en posteriores acciones por parte del usuario.
- Administración del club por parte del usuario, lo cual incluye agregar o quitar jugadores, agregar, quitar o editar comportamientos, editar el nombre  y avatar del club y predefinir una plantilla default para jugar partidos.
- Sistema de estadísticas de clubes. En este muestran, por club, goles a favor y en contra, cantidad de ligas y partidos amistosos jugados,cantidad de ligas y partidos amistosos ganado y cantidad de puntos totales.

### Jugadores, comportamientos y plantillas:

- Sistema de atributos fijos para jugadores, donde cada jugador tiene cinco atributos: Power, Agility, Control, Speed y Strength (PACSS). Los valores asignados deberán respetar las restricciones establecidas por el sistema. 
- Sistema de comportamientos para jugadores. Estos comportamientos se encuentran asociados a cada club, los cuales consisten en código escrito en lenguaje Python por los usuarios para modelar cómo interactúan sus jugadores durante determinados momentos dentro de un partido. 
- Los comportamientos se pueden crear, editar, eliminar y el club puede tener una cantidad limitada de ellos.
- El usuario es provisto por el sistema de datos del partido en cada momento y de funciones primitivas para definir y ejecutar los comportamientos. Los datos del partido incluyen posición de todos los jugadores, posición de la pelota y estadísticas del partido (cantidad de goles, tiempo actual y total).
- La información sobre los comportamientos programados por el usuario para sus jugadores es privada, es decir, un usuario no puede ver el comportamiento de jugadores que no sean de su equipo.
- El usuario podrá crear y almacenar una plantilla default de juego. La misma estará compuesta por una formación, tres jugadores titulares, tres jugadores suplentes y un comportamiento inicialmente asignado a cada jugador titular.
- La plantilla podrá ser creada y editada, y se le solicitará al usuario que elija entre esa plantilla o poder editarla al momento de participar en ligas o partidos amistosos.  Al momento de entrar a una liga, el usuario elige si utilizar esa plantilla predeterminada o editarla para “generar” una nueva, la cual mantendrá durante toda la liga. Al unirse a un partido amistoso, podrá o utilizar la plantilla predeterminada o editarla para “generar” una nueva plantilla que se mantendrá durante ese partido.

### Partido:

- Los partidos siempre se juegan entre dos usuarios en tiempo real, y deben poder observarse en la aplicación mientras suceden. 
- Los jugadores dentro de un partido ejecutan su comportamiento asignado en determinados momentos del partido.
- Los comportamientos se almacenan y computan completamente en el servidor cuando se efectúan en un partido. El cliente solo indica cual utilizar.
- La cancha es representada por una matriz rectangular, inmutable y definida por el sistema.
- Durante los partidos, el usuario puede cambiar los comportamientos que tienen asignados sus jugadores tantas veces como quiera. El cambio de comportamiento ocurre inmediatamente.
- Cada partido tiene una duración previamente establecida por el usuario anfitrión, ya sea al crear una liga o al crear un partido amistoso.
- El partido está dividido en tiempos (dos pausas de hidratación y un entretiempo), en los cuales el usuario puede realizar solo una sustitución por cada uno de estos. 
- Un usuario  puede salir y volver a entrar a visualizar el partido que aún se esté jugando.
- Un usuario puede participar en múltiples partidos al mismo tiempo, y cada jugador seguirá ejecutando el comportamiento que le haya sido asignado incluso si el usuario deja de visualizar el partido.
- Un usuario puede observar partidos en curso entre otros usuarios. Esto se permite sólo si tales partidos pertenecen a ligas públicas o partidos amistosos , o si estos partidos forman parte de las ligas privadas en las que el usuario participa.

### Ligas y partidos amistosos:

- Un usuario puede crear o unirse a dos modos de juego: Ligas o Partidos amistosos.
- Las ligas consisten en competencias de múltiples usuarios (mínimo tres), donde cada usuario juega un partido con cada usuario diferente de él (con un fixture generado por el sistema) y disputa una tabla de posiciones. 
- Los partidos amistosos consisten en un partido uno contra uno.
- Los partidos amistosos son exclusivamente públicos, mientras que las ligas pueden ser públicas o privadas (en donde se requerirá una contraseña)
- Ganar un partido le otorga al usuario 3 puntos, empatarlo 1 punto y perderlo 0 puntos. Estos puntos cuentan tanto para el ranking de la liga a  la que pertenezca el partido, como para el ranking global (mientras la liga sea publica).
- El usuario debe presentar un equipo predeterminado para unirse a ligas o partidos amistosos. Esto implica elegir tres jugadores titulares (cada uno con su propio comportamiento) y tres suplentes. Para ello se le permitirá a cada usuario formar una plantilla predeterminada,  las cuales definen los seis jugadores, los comportamientos iniciales de los jugadores titulares y el posicionamiento de los mismos (elegido a partir de opciones dadas por el sistema)


## Restricciones:

### Técnicas:

- No está permitido utilizar polling.
- El backend deberá realizarse utilizando FastAPI y SQLAlchemy.
- El frontend deberá realizarse utilizando React.
- La arquitectura del sistema debe ser cliente-servidor.
- El código de los comportamientos de los jugadores deberá ejecutarse en el -servidor y no en el cliente.
- Los rankings deberán mantenerse actualizados por el sistema, y no calcularse completamente cada vez que el usuario quiera verlo.
- Una vez que el usuario está participando dentro de un partido, no puede crear, editar o eliminar comportamientos y jugadores. Tampoco puede renombrar el club o editar el avatar del mismo.

### Características:

- Edición de características extras de equipo más allá de quitar o agregar jugadores y comportamientos (limitar cantidad de jugadores en partido, etc.).
- El partido entre dos jugadores no cuenta con árbitros, faltas, offside, laterales, penales y la pelota no abandona el campo de juego.
- Exportar/importar datos sobre el propio club u otros.
- No se proveerá sistema de notificaciones.
- El código de los comportamientos de los jugadores deberá estar regulado y construirse a partir de primitivas por motivos de seguridad y comunicación con el servidor.
- Modo invitado / Guest Mode (permite jugar sin crear/iniciar sesión con una cuenta) 
- No hay partidos amistosos con contraseña.
- No se pueden visualizar partidos concluidos.
- Las estadísticas obtenidas de ligas privadas no se utilizan para actualizar los valores del ranking global de clubes.
- Un usuario espectador (participante del partido o no) no puede ser expulsado por otro (sea anfitrión o no).