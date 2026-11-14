// Historias del blog. Se editan a mano (una vez al mes) y se publican con deploy.
// La más nueva va primero. Campos:
//   slug     dirección: /blog/<slug> (minúsculas, números y guiones; no cambiarlo una vez publicado)
//   fecha    AAAA-MM-DD
//   ciudad, region   la región arma las secciones del menú y de la portada
//   foto     id de Unsplash ("1502602898657-3e91760cbb34") o la url completa de una imagen
//   cuerpo   una línea = un bloque:
//              párrafo normal
//              ## Subtítulo
//              > Frase destacada
//              ![Pie de la foto](id de Unsplash o url)
//   consejos van abajo de la historia, con tu enlace de afiliado en "enlace" (de Travelpayouts > Herramientas > Campo de golf: https://<marca>.tpx.gr/...)
// Para que no se parezcan entre sí, cada historia usa un formato distinto: un día de hora en hora,
// una lista numerada, un recorrido por la comida, preguntas frecuentes, una sola experiencia, barrios.
// Largo de referencia: 600 a 800 palabras.
export default [
  {
    // Formato: un día de hora en hora.
    slug: "un-dia-perfecto-en-cartagena",
    fecha: "2026-11-01",
    ciudad: "Cartagena",
    region: "Sudamérica",
    foto: "1536308037887-165852797016",
    autor: "Equipo Buscavuelosbaratos",
    titulo: "Un día perfecto en Cartagena, de hora en hora",
    resumen: "Murallas, balcones con flores, frutas tropicales y un atardecer sobre el Caribe: un día completo en la joya colonial de Colombia.",
    cuerpo: `
Cartagena de Indias se vive con calor, despacio y a pie. Su ciudad amurallada es una de las más bonitas de América: calles de piedra, casas de colores con balcones de madera cubiertos de buganvilias y plazas donde siempre suena música.

El sol del Caribe manda aquí. Al mediodía el calor aprieta y los cartageneros se refugian a la sombra, así que el secreto es madrugar, descansar en las horas fuertes y salir de nuevo cuando baja el sol. Este es un plan para un día redondo.

## 7:00 · La ciudad antes que nadie
Sal temprano, cuando las calles todavía están vacías y la luz es suave. Es la mejor hora para fotografiar las fachadas amarillas, azules y rosadas sin turistas en el encuadre, y para caminar sin sudar.

Entra a la ciudad por la Torre del Reloj, la puerta principal de la muralla. Del otro lado está la Plaza de los Coches, donde en la época colonial funcionó el mercado de esclavos, una historia dura que conviene conocer para entender la ciudad.

![La Torre del Reloj, entrada a la ciudad amurallada](1767743364534-15bf2ea67781)

## 8:30 · Desayuno costeño
Busca una arepa de huevo: masa de maíz frita, rellena con un huevo entero y frita otra vez. Es el desayuno de la costa colombiana, se compra en puestos callejeros y se come caliente, con cuidado de no quemarte.

Acompáñala con un jugo de fruta natural. En Cartagena hay frutas que quizá nunca has probado, como el lulo, el corozo o la guanábana.

## 10:00 · Plazas y palenqueras
Recorre las plazas del centro: la de Santo Domingo, con la escultura de una mujer recostada que donó Fernando Botero, la de San Pedro Claver y la de Bolívar, la más sombreada.

En el camino vas a ver a las palenqueras, mujeres con vestidos de colores y una palangana de frutas en la cabeza. Vienen de San Basilio de Palenque, el primer pueblo libre de América, fundado por esclavos que escaparon. Si les tomas una foto, lo justo es comprarles fruta o dejarles una propina.

![Palenqueras con vestidos de colores en una calle de Cartagena](1678794143765-cf91f5d0ae1d)

## 13:00 · Almuerzo y siesta
A esta hora el sol no perdona. Busca un restaurante de barrio con menú del día: casi siempre hay pescado frito, arroz con coco, patacones y ensalada. Para tomar, una limonada de coco, la bebida más refrescante de la ciudad.

Después, haz lo que hacen los locales: descansa. Vuelve al hotel, métete a la piscina o busca una hamaca. La tarde es larga.

## 16:00 · El Castillo de San Felipe
Cuando baje el calor, toma un taxi corto hasta el Castillo de San Felipe de Barajas, la fortaleza más grande que construyeron los españoles en sus colonias. Se levantó para defender la ciudad de los piratas y de las flotas inglesas.

Recorre sus rampas y túneles, diseñados para que el sonido de los pasos delatara a cualquier invasor. Desde lo alto se ve toda la ciudad.

![El Castillo de San Felipe sobre la colina](1657465141082-2f0b05096648)

## 17:30 · Atardecer en la muralla
Regresa a la ciudad amurallada y sube a la muralla, que rodea el centro por casi once kilómetros. Busca un lugar mirando al mar y espera: el sol se hunde en el Caribe y el cielo se pone naranja, rosa y morado.

> En Cartagena el atardecer se mira desde la muralla, con el mar de frente y la ciudad a la espalda.

![La ciudad vista desde lo alto de la muralla](1633394027858-fff49145f120)

## 20:00 · Noche en Getsemaní
Cierra el día en Getsemaní, el barrio que está justo afuera de la muralla. Antes era una zona humilde y hoy es el más vivo de la ciudad: calles con paraguas colgados, murales enormes y bares pequeños.

En la Plaza de la Trinidad, por la noche, se juntan vecinos, viajeros, vendedores de comida y músicos. Pide una empanada o un pincho, siéntate en las escaleras de la iglesia y deja que Cartagena haga el resto.
`,
    consejos: [
      { titulo: "Tour a las Islas del Rosario", texto: "La escapada de playa más famosa desde Cartagena: compara tours antes de ir al muelle.", marca: "Klook", enlace: "https://klook.tpx.gr/VLyjwPF5" },
      { titulo: "Traslado desde el aeropuerto", texto: "Con precio cerrado y sin buscar taxi con el calor al aterrizar.", marca: "Kiwitaxi", enlace: "https://kiwitaxi.tpx.gr/r2COdaGz" },
      { titulo: "Lleva datos desde que aterrizas", texto: "Con una eSIM tienes mapas y apps de transporte desde el primer minuto.", marca: "Yesim", enlace: "https://yesim.tpx.gr/iQxdxX60" },
    ],
  },
  {
    // Formato: lista numerada.
    slug: "7-planes-en-cancun-sin-todo-incluido",
    fecha: "2026-10-01",
    ciudad: "Cancún",
    region: "Norteamérica y Caribe",
    foto: "1602088113235-229c19758e9f",
    autor: "Equipo Buscavuelosbaratos",
    titulo: "7 planes en Cancún que no necesitan todo incluido",
    resumen: "Playas abiertas a todos, una isla a 20 minutos y agua turquesa bajo tierra. El Caribe mexicano, sin pulsera.",
    cuerpo: `
En México todas las playas son públicas. Ese dato, que muchos viajeros no conocen, cambia por completo la forma de vivir Cancún: aunque frente a ti haya un hotel de veinte pisos, la arena y el mar son de todos, y el hotel está obligado a dejar pasar.

El todo incluido tiene su encanto, pero también tiene un precio: te encierra en un mismo lugar y te deja ver muy poco de lo que hace especial a esta parte del Caribe. Estos son siete planes para disfrutarlo por tu cuenta, a tu ritmo y gastando bastante menos.

## 1. Playa Delfines
Es la favorita de los locales y una de las pocas de la zona hotelera sin edificios encima. Desde el mirador de la carretera se ve la playa completa, con el mar en todos los tonos de turquesa que existen, y ahí está también el famoso letrero de colores de Cancún para la foto.

Abajo, la arena es blanca y fina, y casi siempre hay espacio de sobra. Ojo: el oleaje puede ser fuerte. Fíjate en las banderas de los salvavidas antes de meterte al agua.

## 2. Moverte en el R1
Los autobuses R1 y R2 recorren toda la zona hotelera y el centro de la ciudad, pasan cada pocos minutos y cuestan una fracción de un taxi. Funcionan desde muy temprano hasta tarde en la noche.

Lleva el pasaje en efectivo y en monedas, y avísale al chofer dónde te bajas. Es la forma más práctica de ir de playa en playa y de llegar al centro para comer.

## 3. Isla Mujeres en carrito de golf
Desde Puerto Juárez sale un ferry cada media hora, más o menos, y en unos 20 minutos te deja en Isla Mujeres. Es pequeña, colorida y mucho más tranquila que Cancún.

Lo clásico es rentar un carrito de golf y recorrerla completa, de punta a punta, en una tarde. Hay calles de casas pintadas, tiendas de artesanías y miradores donde el mar se ve de un azul imposible.

![La orilla de Isla Mujeres entre palmeras](1545591853-dd70186241e9)

Al sur está Punta Sur, el acantilado donde, dicen, sale el primer sol de México. Hay un pequeño parque de esculturas y un sendero sobre las rocas con el mar abierto rompiendo abajo.

## 4. Atardecer en Playa Norte
Vuelve hacia el norte de la isla para el final del día. Playa Norte tiene el agua tan baja y transparente que puedes caminar varios metros mar adentro sin que te llegue a la cintura.

Es una de las pocas playas de la zona donde el sol se pone sobre el mar. Compra algo de beber en un puesto, busca un lugar en la arena y quédate hasta que se ponga. Toma el último ferry de vuelta con tiempo.

## 5. La Ruta de los Cenotes
Los cenotes son pozos naturales de agua dulce que se forman cuando colapsa el techo de una cueva. La península de Yucatán tiene miles, y para los mayas eran entradas sagradas al inframundo.

Cerca de Puerto Morelos, a menos de una hora de Cancún, está la Ruta de los Cenotes: una carretera en plena selva con varios de ellos abiertos al público, algunos a cielo abierto y otros dentro de cavernas.

![Un cenote de agua azul dentro de una cueva](1719941463960-f3310fe64e46)

Bajar a uno es como entrar a otro planeta: silencio, raíces colgando del techo y un agua tan clara que ves el fondo a varios metros. Lleva traje de baño, una toalla y, sobre todo, nada de bloqueador ni repelente: la mayoría pide ducharse antes de entrar para no contaminar el agua.

## 6. Tulum frente al mar
Las ruinas de Tulum son las únicas de la gran cultura maya construidas frente al mar. Su castillo, sobre un acantilado de roca y con el Caribe turquesa de fondo, es una de las imágenes más famosas de México.

Quedan a unas dos horas en auto. Llega temprano, apenas abran, antes del calor y de los autobuses de excursión. Al terminar, baja a la pequeña playa que hay al pie de las ruinas.

![El castillo de Tulum sobre el mar](1665618980645-ca9cd5e68508)

## 7. Cenar en el centro
Para cerrar el viaje, deja la zona hotelera y cena donde cenan los cancunenses: en el Parque de las Palapas, en el centro de la ciudad.

Al caer la noche se llena de familias y de puestos de comida. Prueba una marquesita, un crujiente rollo de barquillo relleno de queso de bola y cajeta o Nutella, y unos esquites con limón y chile. Después, busca una taquería cercana. Vas a comer muy bien por poco dinero, y vas a ver el Cancún que no sale en los folletos.
`,
    consejos: [
      { titulo: "Reserva el traslado del aeropuerto", texto: "Con precio cerrado antes de llegar evitas regatear al salir.", marca: "Kiwitaxi", enlace: "https://kiwitaxi.tpx.gr/r2COdaGz" },
      { titulo: "Renta un auto para los cenotes", texto: "Para Tulum y los cenotes un auto te da libertad de horarios.", marca: "Localrent", enlace: "https://localrent.tpx.gr/CsEUSLBU" },
      { titulo: "Tours a Isla Mujeres", texto: "Compara tours y ferry antes de ir al muelle.", marca: "Klook", enlace: "https://klook.tpx.gr/VLyjwPF5" },
    ],
  },
  {
    // Formato: recorrido por la comida.
    slug: "ciudad-de-mexico-se-come",
    fecha: "2026-09-01",
    ciudad: "Ciudad de México",
    region: "Norteamérica y Caribe",
    foto: "1597462314428-609c6581247e",
    autor: "Equipo Buscavuelosbaratos",
    titulo: "Ciudad de México se come: 5 sabores que no te puedes perder",
    resumen: "Tacos de madrugada, tamales en la esquina y churros con chocolate: la capital mexicana se conoce mejor con hambre.",
    cuerpo: `
La Ciudad de México tiene museos de primer nivel, pirámides a una hora y uno de los centros históricos más grandes de América. Pero si le preguntas a cualquiera que la haya visitado qué fue lo mejor, casi siempre te va a hablar de la comida.

Aquí se come en la calle, a toda hora y por muy poco dinero. En cada esquina hay un puesto, en cada mercado una fonda, y cada barrio tiene su taquería favorita que defiende como si fuera un equipo de fútbol.

> En la Ciudad de México, la mejor comida casi nunca tiene mantel.

Un consejo antes de empezar: fíjate dónde hay fila de locales. Si un puesto está lleno de oficinistas, taxistas y familias, es buena señal. Y lleva efectivo en billetes pequeños, porque muchos puestos no aceptan tarjeta.

## Tacos al pastor
Son el símbolo de la ciudad. La carne de cerdo se marina con chiles secos y achiote, se apila en un trompo vertical y se asa lentamente frente a una llama, con una piña en lo alto.

El taquero corta láminas finas directo sobre una tortilla pequeña de maíz, y con un movimiento rápido lanza un trozo de piña encima. Se sirven con cebolla, cilantro y salsa al gusto. La técnica la trajeron los inmigrantes libaneses, y los mexicanos la convirtieron en otra cosa.

![Tacos con limón sobre una tabla de madera](1648437595587-e6a8b0cdf1f9)

Los mejores se comen de noche, de pie junto al trompo. Pide "con todo" y no te limites a uno: aquí los tacos se piden de tres en tres.

## Tamales y atole
Por la mañana, en muchas esquinas aparece un puesto con una olla humeante. Son los tamales: masa de maíz rellena de salsa verde, mole o rajas con queso, envuelta en hoja de maíz y cocida al vapor.

Acompáñalos con un atole, una bebida caliente y espesa de maíz con sabores como chocolate, vainilla o fresa. Y si quieres desayunar como chilango, pide una guajolota: un tamal dentro de un pan. Sí, carbohidrato dentro de carbohidrato. Y funciona.

## Quesadillas y antojitos de mercado
Los mercados son el corazón de la cocina diaria. En sus fondas, señoras que cocinan desde hace décadas preparan quesadillas, sopes, tlacoyos y gorditas frente a ti, sobre un comal caliente.

![Una cocinera prepara comida en un puesto de mercado](1545504573-edac76c6a487)

Un dato que confunde a todos los visitantes: en la Ciudad de México las quesadillas no siempre llevan queso. Si lo quieres, tienes que pedirlo. Prueba las de flor de calabaza, de huitlacoche, un hongo del maíz que es una delicia, o de chicharrón prensado.

El Mercado de Coyoacán es famoso por sus tostadas, y en el centro, el Mercado de San Juan es el paraíso de los ingredientes raros.

## Esquites y elotes
Al caer la tarde, sobre todo en plazas y parques, aparecen los carritos de esquites y elotes. El elote es la mazorca entera, cocida y untada con mayonesa, queso rallado, chile en polvo y limón.

Los esquites son los granos de maíz desgranados, cocidos en caldo con epazote y servidos en vaso con los mismos ingredientes. Son el antojito perfecto para comer caminando por Coyoacán o el centro.

## Churros con chocolate
Para el postre, el clásico de clásicos: churros recién hechos, crujientes por fuera y suaves por dentro, espolvoreados con azúcar y canela, para mojar en una taza de chocolate caliente.

En el centro histórico hay churrerías que abren desde la mañana hasta la noche y que llevan generaciones friendo churros a la vista de todos. Son el mejor cierre para un día de caminata.

![Churros recién hechos con azúcar](1505851498219-ee2449c18936)

Al final del viaje vas a descubrir algo: en esta ciudad nunca te quedas con hambre, pero siempre te quedas con ganas de volver.
`,
    consejos: [
      { titulo: "Tour de comida callejera", texto: "Un recorrido guiado por puestos y mercados para probar mucho sin equivocarte.", marca: "Klook", enlace: "https://klook.tpx.gr/VLyjwPF5" },
      { titulo: "Traslado desde el aeropuerto", texto: "Reservado de antemano, con precio cerrado hasta tu hotel.", marca: "Kiwitaxi", enlace: "https://kiwitaxi.tpx.gr/r2COdaGz" },
      { titulo: "Datos para buscar dónde comer", texto: "Con una eSIM tienes mapas y reseñas en el teléfono desde que aterrizas.", marca: "Yesim", enlace: "https://yesim.tpx.gr/iQxdxX60" },
    ],
  },
  {
    // Formato: preguntas frecuentes.
    slug: "bogota-para-primerizos",
    fecha: "2026-08-01",
    ciudad: "Bogotá",
    region: "Sudamérica",
    foto: "1568632234157-ce7aecd03d0d",
    autor: "Equipo Buscavuelosbaratos",
    titulo: "Bogotá para primerizos: lo que todos preguntan antes de ir",
    resumen: "¿Hace frío? ¿Afecta la altura? ¿Qué no te puedes perder? Respuestas claras para tu primer viaje a la capital colombiana.",
    cuerpo: `
Bogotá suele tomar por sorpresa a quien llega pensando en el Caribe colombiano. No hay playa ni calor tropical: es una ciudad de montaña, enorme, cultural y con un clima propio, rodeada de cerros verdes que se ven desde casi cualquier esquina.

También es una de las capitales más interesantes de América Latina para viajar con poco presupuesto. Tiene museos de primer nivel que no cobran entrada, una escena gastronómica en plena ebullición y barrios que se recorren muy bien a pie. Estas son las dudas que más se repiten antes del primer viaje.

## ¿Hace frío de verdad?
Sí, pero no tanto como imaginas. La temperatura ronda los 14 grados casi todo el año, porque Bogotá está cerca del ecuador y no tiene estaciones como tal.

Lo que sí cambia, y mucho, es el clima a lo largo del día. Las mañanas son frescas, al mediodía el sol pega fuerte y por la tarde suele llover. Los bogotanos dicen que en un mismo día se pueden vivir las cuatro estaciones.

La regla local es vestirse por capas: una camiseta, un suéter y una chaqueta impermeable que puedas guardar. Y siempre, siempre, un paraguas.

## ¿Me va a afectar la altura?
La ciudad está a unos 2.600 metros sobre el nivel del mar, más alta que muchas estaciones de esquí. A la mayoría de los viajeros no les pasa nada grave, pero es normal sentir algo de cansancio, falta de aire al subir escaleras o un leve dolor de cabeza el primer día.

Tómatelo con calma: camina despacio, toma mucha agua, come ligero y modera el alcohol las primeras 24 horas. Deja los planes más exigentes, como subir a Monserrate, para el segundo o tercer día.

## ¿Qué no me puedo perder?
Empieza por La Candelaria, el centro histórico. Es el barrio más antiguo de la ciudad, con casas coloniales de colores, calles empinadas y empedradas, y murales enormes que convierten cada cuadra en una galería a cielo abierto. Un recorrido de grafiti con guía es una de las mejores formas de entender la historia reciente del país.

![Paraguas de colores sobre una calle de Bogotá](1759375333229-f11b52711d73)

Ahí mismo está el Museo Botero, que no cobra entrada. Además de las famosas figuras voluminosas del artista colombiano, guarda la colección que él mismo donó, con obras de Picasso, Monet, Renoir y Dalí. A pocas cuadras está el Museo del Oro, con miles de piezas de orfebrería prehispánica que brillan en la penumbra.

Después, sube a Monserrate. El cerro tiene 3.152 metros de altura y se puede subir en teleférico o en funicular, o a pie si estás bien aclimatado. Arriba hay un santuario, puestos de comida típica y una vista de la ciudad entera, que se extiende hasta perderse en la sabana.

![Bogotá vista desde lo alto de Monserrate](1738474429313-239cbf1687fd)

Ya que estás ahí, haz lo que hacen los locales: pide un chocolate caliente con queso. Sí, se mete el queso dentro del chocolate, se deja derretir y se come con cuchara. Suena raro y es delicioso.

## ¿Qué tengo que comer?
El plato insignia de la ciudad es el ajiaco: una sopa espesa de pollo con tres tipos de papa, mazorca y una hierba local llamada guasca, que se sirve con crema, alcaparras y aguacate. Es perfecta para el clima frío.

Para el desayuno, prueba una changua, una sopa de leche con huevo, o unas arepas con queso. Y en cualquier panadería, pide un tinto, como llaman aquí al café negro, con un pandebono recién horneado.

## ¿Cómo me muevo?
El TransMilenio, el sistema de buses rápidos con carriles exclusivos, llega a casi toda la ciudad. Es barato y eficiente, aunque en hora pico va muy lleno, así que vigila tus cosas.

Para trayectos cortos, para ir y volver del aeropuerto y siempre de noche, las aplicaciones de transporte son lo más práctico y seguro.

## ¿Y si me toca domingo?
Mejor todavía. Cada domingo y día festivo, la ciclovía cierra más de cien kilómetros de avenidas a los autos para que las usen ciclistas, patinadores y peatones. Renta una bicicleta y súmate a los miles de bogotanos que salen a pedalear: es la mejor forma de ver la ciudad como un local.

Por la tarde, ve a Usaquén. Este antiguo pueblo, hoy absorbido por la ciudad, conserva su plaza y su iglesia, y los domingos se llena con un mercado de pulgas de artesanías, música y comida. Un buen cierre para un primer viaje que, seguramente, no será el último.
`,
    consejos: [
      { titulo: "Tour por La Candelaria", texto: "Un recorrido guiado ayuda a entender la historia del centro y de sus murales.", marca: "Klook", enlace: "https://klook.tpx.gr/VLyjwPF5" },
      { titulo: "eSIM para moverte con apps", texto: "Con datos puedes pedir transporte por aplicación desde el aeropuerto.", marca: "Yesim", enlace: "https://yesim.tpx.gr/iQxdxX60" },
      { titulo: "Traslado desde El Dorado", texto: "Reservado de antemano, con precio cerrado y sin buscar taxi al llegar.", marca: "Kiwitaxi", enlace: "https://kiwitaxi.tpx.gr/r2COdaGz" },
    ],
  },
  {
    // Formato: una sola experiencia, contada de principio a fin.
    slug: "cruzar-el-puente-de-brooklyn-al-atardecer",
    fecha: "2026-07-01",
    ciudad: "Nueva York",
    region: "Norteamérica y Caribe",
    foto: "1496588152823-86ff7695e68f",
    autor: "Equipo Buscavuelosbaratos",
    titulo: "Cruzar el puente de Brooklyn al atardecer",
    resumen: "Media hora a pie, casi dos kilómetros de tablas de madera y el skyline más famoso del mundo encendiéndose frente a ti. Gratis.",
    cuerpo: `
Hay planes en Nueva York que cuestan una fortuna: miradores en lo alto de rascacielos, espectáculos de Broadway, cenas con vista. Este no cuesta nada y es, para muchos viajeros, el mejor momento de todo el viaje.

Se trata de algo tan simple como caminar de un lado a otro de un puente. Pero no de cualquier puente, ni a cualquier hora.

## Un puente con historia
Cuando se inauguró en 1883, el puente de Brooklyn era el puente colgante más largo del mundo y una de las grandes obras de ingeniería de su época. Tardó catorce años en construirse y unió por primera vez dos ciudades que entonces eran independientes: Nueva York y Brooklyn.

Su historia tiene mucho de novela. El ingeniero que lo diseñó, John Roebling, murió antes de que empezaran las obras. Su hijo Washington tomó el relevo, pero enfermó gravemente y tuvo que dirigir la construcción desde la ventana de su casa. Fue su esposa, Emily, quien llevaba las instrucciones a la obra día tras día, y fue también la primera persona en cruzar el puente terminado.

![El puente de Brooklyn iluminado de noche](1477882244523-716124bf91a1)

## El secreto está en la dirección
Casi todo el mundo cruza desde Manhattan hacia Brooklyn, y se pierde lo mejor. El truco es hacerlo al revés: de Brooklyn hacia Manhattan. Así caminas con los rascacielos de frente, creciendo a cada paso, en lugar de dejarlos a tu espalda.

Para eso, toma el metro hasta Brooklyn y empieza en Dumbo, el barrio de ladrillo y adoquines que queda justo debajo del puente. Su nombre es un acrónimo en inglés de "debajo de la rampa del puente de Manhattan", y hasta hace unas décadas era una zona de fábricas y almacenes. Hoy tiene galerías, cafés y parques junto al agua.

Llega una hora antes de la puesta de sol. Así tendrás tiempo de tomar la foto clásica en la esquina de Washington Street y Water Street, con el puente de Manhattan enmarcado entre dos edificios, y de bajar al parque junto al río para ver el skyline desde la orilla.

![El puente de Manhattan entre los edificios de ladrillo de Dumbo](1791106702041-f4698f18e649)

> Camina de Brooklyn a Manhattan: el skyline te espera de frente.

## La caminata
Desde Dumbo, sigue las indicaciones hasta la entrada de la pasarela peatonal. Desde 2021 los ciclistas tienen su propio carril a nivel de la calzada, así que la pasarela elevada de madera es solo para caminar, algo que se agradece.

El recorrido es de casi dos kilómetros. A paso tranquilo, con paradas para fotos, tardarás entre 30 y 40 minutos. Y vas a querer detenerte a cada rato.

Lo primero que impresiona son las torres de piedra, con sus arcos góticos que parecen de una catedral. Después, la telaraña de cables de acero que baja desde lo alto y que, vista desde abajo, parece dibujada con regla. Bajo tus pies, entre las tablas, se alcanza a ver el tráfico y, más abajo todavía, el agua.

![Los cables de acero y una de las torres de piedra del puente](1659463964171-850d7f507602)

## El momento
A medio camino empieza lo mejor. El cielo se pone naranja y luego rosado, el agua del East River se vuelve dorada y, una a una, se encienden las ventanas de los rascacielos de Manhattan.

A tu izquierda, a lo lejos, se distingue la Estatua de la Libertad. A tu derecha, el puente de Manhattan y, más allá, las torres de Midtown. Alrededor, gente de todo el mundo hace exactamente lo mismo que tú: detenerse, mirar y no decir nada.

![El skyline de Manhattan iluminado al otro lado del agua](1783372935296-2e78e61a0894)

## Al otro lado
Cuando bajes en el lado de Manhattan ya será de noche. Estarás junto al ayuntamiento y a pocos minutos a pie de Chinatown, el mejor lugar de la zona para una cena barata: dumplings, sopas de fideos y panaderías donde se come muy bien por pocos dólares.

![Farolillos y tiendas en una calle de Chinatown](1772374998642-a6c0b540086b)

Un último consejo: evita el puente los fines de semana a media tarde, cuando se llena tanto que cuesta avanzar. Entre semana, al atardecer, es otra experiencia. Y si quieres repetir, hazlo al amanecer: casi no hay nadie y la luz sobre Manhattan es igual de mágica.
`,
    consejos: [
      { titulo: "Pase de atracciones", texto: "Si además vas a subir a un mirador y entrar a museos, un pase combinado puede salir más barato.", marca: "Tiqets", enlace: "https://tiqets.tpx.gr/SBNJhGb5" },
      { titulo: "Traslado desde el aeropuerto", texto: "Reservado de antemano, sin sorpresas al llegar a JFK o Newark.", marca: "Kiwitaxi", enlace: "https://kiwitaxi.tpx.gr/r2COdaGz" },
      { titulo: "Hotel en Brooklyn", texto: "Suele salir más barato que Manhattan y queda a pocas paradas de metro.", marca: "Klook", enlace: "https://klook.tpx.gr/VLyjwPF5" },
    ],
  },
  {
    // Formato: recorrido por barrios.
    slug: "lima-en-tres-barrios",
    fecha: "2026-06-01",
    ciudad: "Lima",
    region: "Sudamérica",
    foto: "1777198498604-a924324d1eb2",
    autor: "Equipo Buscavuelosbaratos",
    titulo: "Lima en tres barrios",
    resumen: "El centro colonial, los acantilados de Miraflores y el Barranco bohemio: tres caras de una ciudad que se come de maravilla.",
    cuerpo: `
Muchos viajeros pasan por Lima solo de camino a Cusco y Machu Picchu: aterrizan, duermen una noche cerca del aeropuerto y siguen viaje. Es un error. La capital peruana tiene cinco siglos de historia, una costa espectacular sobre el Pacífico y una de las cocinas más celebradas del mundo.

Es una ciudad enorme, de más de diez millones de habitantes, y puede abrumar al principio. Pero para entenderla basta con recorrer tres barrios, cada uno con su propia personalidad.

## El Centro Histórico
Lima fue durante casi tres siglos la capital del virreinato del Perú, la ciudad más rica e importante de Sudamérica. Su centro histórico guarda esa memoria, y por eso es Patrimonio de la Humanidad.

El corazón es la Plaza Mayor, también llamada Plaza de Armas. A su alrededor están la Catedral, el Palacio de Gobierno, el Palacio Arzobispal y algunos de los famosos balcones de madera tallada que, cerrados con celosías, permitían mirar la calle sin ser visto.

![La Plaza Mayor de Lima](1716116112529-3e9f2d050ed9)

Si llegas cerca del mediodía, frente al Palacio de Gobierno se hace el cambio de guardia, con banda de música y uniformes de gala.

A pocas cuadras está el Convento de San Francisco, uno de los conjuntos coloniales más bellos de la ciudad. Tiene una biblioteca antigua que parece salida de una película y, bajo tierra, unas catacumbas que funcionaron como cementerio durante la colonia. Se visitan con guía y no son para todos, pero no se olvidan.

Para almorzar en el centro, busca un chifa en el Barrio Chino, junto al Mercado Central. La comida chino-peruana es una de las grandes fusiones de la cocina local, y aquí se come abundante y barato.

## Miraflores
Al sur, Lima se asoma al Pacífico desde lo alto de los acantilados. Miraflores es el barrio más moderno y cuidado, con parques, cafés y edificios frente al mar.

Su gran atractivo es el malecón: varios kilómetros de parques y senderos sobre el acantilado, ideales para caminar, correr o andar en bicicleta. Desde ahí se ven los parapentes que despegan sobre el mar y los surfistas que esperan su ola allá abajo.

Haz una pausa en el Parque del Amor, con su enorme escultura de una pareja besándose y sus bancas cubiertas de mosaicos con frases románticas. Después sigue caminando hasta Larcomar, un centro comercial construido dentro del propio acantilado.

> En Lima, el atardecer sobre el Pacífico es un plan en sí mismo.

Un dato curioso: en Lima casi nunca llueve. Pero durante buena parte del año el cielo está cubierto por una neblina gris que los limeños llaman "panza de burro". Si te toca, no te desanimes: en verano, de diciembre a marzo, el sol vuelve y los atardeceres son espectaculares.

## Barranco
Siguiendo el malecón hacia el sur, en pocos minutos llegas a Barranco. A fines del siglo XIX era el balneario de veraneo de las familias ricas de Lima. Hoy es el barrio de artistas, poetas y músicos.

Sus calles están llenas de casonas de colores, algunas restauradas y otras con el encanto del abandono, y de murales que cubren paredes enteras. Hay galerías, museos pequeños y librerías.

![Casas de colores en una calle de Barranco](1508958156594-61260a92449e)

El símbolo del barrio es el Puente de los Suspiros, un puente de madera sobre una antigua bajada hacia el mar. Dice la leyenda que si lo cruzas por primera vez aguantando la respiración, se cumple tu deseo.

De noche, Barranco cambia de ritmo: se llenan sus bares pequeños y sus peñas, donde se escucha música criolla y afroperuana en vivo.

## ¿Dónde comer bien y barato?
Este es el verdadero secreto de Lima: el menú del día. En las cevicherías y restaurantes de barrio, a la hora del almuerzo, por poco dinero te sirven entrada, plato de fondo y una bebida.

![Un plato fresco de ceviche](1535399831218-d5bd36d1a6b3)

Pide un ceviche clásico: pescado fresco cortado en cubos, marinado unos minutos en jugo de limón, con cebolla morada, ají, camote y choclo. El jugo que queda en el plato se llama leche de tigre y muchos lo toman directo del vaso.

Y hazlo al mediodía, como hacen los limeños. El ceviche se come de día, cuando el pescado está recién llegado del mar. Pedirlo de noche es la forma más rápida de que te reconozcan como turista.
`,
    consejos: [
      { titulo: "Tour gastronómico", texto: "Una buena forma de probar varios platos típicos en una tarde.", marca: "Klook", enlace: "https://klook.tpx.gr/VLyjwPF5" },
      { titulo: "Hotel en Miraflores", texto: "Es la zona más cómoda para moverte a pie entre los tres barrios.", marca: "Klook", enlace: "https://klook.tpx.gr/VLyjwPF5" },
      { titulo: "eSIM para pedir transporte", texto: "Con datos en el teléfono, moverte entre barrios con apps es fácil.", marca: "Yesim", enlace: "https://yesim.tpx.gr/iQxdxX60" },
    ],
  },
];
