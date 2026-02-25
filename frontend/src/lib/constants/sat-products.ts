/**
 * Curated list of ~200 most common SAT product/service codes (c_ClaveProdServ).
 * Used in the invoice line-item combobox.
 */
export const SAT_PRODUCT_KEYS: { value: string; label: string }[] = [
  // ── General ──
  { value: "01010101", label: "01010101 - No existe en el catalogo" },

  // ── Tecnologia y Software ──
  { value: "43231500", label: "43231500 - Software funcional especifico de la empresa" },
  { value: "43231501", label: "43231501 - Software de planificacion de recursos empresariales" },
  { value: "43231503", label: "43231503 - Software de manejo de inventarios" },
  { value: "43231505", label: "43231505 - Software de contabilidad financiera" },
  { value: "43231507", label: "43231507 - Software de compras" },
  { value: "43231508", label: "43231508 - Software de cadena de suministros" },
  { value: "43231509", label: "43231509 - Software de gestion de relaciones con clientes (CRM)" },
  { value: "43231511", label: "43231511 - Software de recursos humanos" },
  { value: "43231512", label: "43231512 - Software de impuestos" },
  { value: "43231513", label: "43231513 - Software de proyectos" },
  { value: "43231601", label: "43231601 - Software de correo electronico" },
  { value: "43232100", label: "43232100 - Software de sistemas operativos" },
  { value: "43232300", label: "43232300 - Software de manejo de licencias" },
  { value: "43232400", label: "43232400 - Software de aplicaciones" },
  { value: "43232402", label: "43232402 - Software de navegador de internet" },
  { value: "43232405", label: "43232405 - Software de servidor web" },
  { value: "43232408", label: "43232408 - Software de aplicacion de base de datos" },
  { value: "43232500", label: "43232500 - Software de comunicaciones" },
  { value: "43232600", label: "43232600 - Software de seguridad y proteccion" },
  { value: "43232700", label: "43232700 - Software de utilidades y dispositivos" },
  { value: "43232800", label: "43232800 - Software de fabricacion y distribucion" },
  { value: "43232900", label: "43232900 - Software de edicion y diseno" },
  { value: "43233000", label: "43233000 - Software educativo y de referencia" },
  { value: "43233200", label: "43233200 - Software de red" },
  { value: "43233400", label: "43233400 - Software de administracion de almacenamiento" },
  { value: "43233500", label: "43233500 - Software de intercambio de informacion" },

  // ── Equipos de Computo ──
  { value: "43211500", label: "43211500 - Computadoras" },
  { value: "43211503", label: "43211503 - Computadoras notebook" },
  { value: "43211507", label: "43211507 - Computadoras de escritorio" },
  { value: "43211508", label: "43211508 - Servidores de computador" },
  { value: "43211509", label: "43211509 - Computadoras tablet" },
  { value: "43212100", label: "43212100 - Impresoras de computador" },
  { value: "43222600", label: "43222600 - Dispositivos de almacenamiento" },
  { value: "43222609", label: "43222609 - Unidades de disco duro" },

  // ── Servicios de Tecnologia ──
  { value: "81111500", label: "81111500 - Ingenieria de software o hardware" },
  { value: "81111501", label: "81111501 - Servicio de programacion de software" },
  { value: "81111502", label: "81111502 - Servicios de diseno de software" },
  { value: "81111503", label: "81111503 - Servicios de administracion de sistemas de computacion" },
  { value: "81111504", label: "81111504 - Programacion de aplicaciones" },
  { value: "81111505", label: "81111505 - Servicios de pruebas de software" },
  { value: "81111506", label: "81111506 - Servicio de soporte tecnico o mesa de ayuda" },
  { value: "81111507", label: "81111507 - Servicios de mantenimiento de software" },
  { value: "81111508", label: "81111508 - Servicios de mantenimiento de hardware" },
  { value: "81111509", label: "81111509 - Servicios de sistemas de informacion" },
  { value: "81111600", label: "81111600 - Programadores de computador" },
  { value: "81111700", label: "81111700 - Servicios de sistemas y administracion de componentes" },
  { value: "81111800", label: "81111800 - Servicios de internet" },
  { value: "81111900", label: "81111900 - Servicios de soporte y hosting" },
  { value: "81112000", label: "81112000 - Servicios de datos" },
  { value: "81112100", label: "81112100 - Internet" },
  { value: "81112200", label: "81112200 - Servicios de analisis de datos" },

  // ── Telecomunicaciones ──
  { value: "83111500", label: "83111500 - Servicios de telecomunicaciones" },
  { value: "83111501", label: "83111501 - Servicios de telefonia movil" },
  { value: "83111502", label: "83111502 - Servicios de telefonia fija" },
  { value: "83111600", label: "83111600 - Servicios de transmision de datos" },

  // ── Consultoria ──
  { value: "80101500", label: "80101500 - Servicios de consultoria de negocios" },
  { value: "80101501", label: "80101501 - Servicio de asesoria en administracion" },
  { value: "80101502", label: "80101502 - Servicio de asesoria en planificacion estrategica" },
  { value: "80101504", label: "80101504 - Servicios de asesoria de comercio exterior" },
  { value: "80101505", label: "80101505 - Servicios de asesoria de gestion industrial" },
  { value: "80101506", label: "80101506 - Servicio de consultoria en logistica" },
  { value: "80101507", label: "80101507 - Servicios de consultoria economica" },
  { value: "80101508", label: "80101508 - Servicios de consultoria ambiental" },
  { value: "80101509", label: "80101509 - Servicios de consultoria en recursos humanos" },
  { value: "80101600", label: "80101600 - Servicios de asesoria gerencial" },
  { value: "80101700", label: "80101700 - Administracion de empresas" },

  // ── Marketing y Publicidad ──
  { value: "80141500", label: "80141500 - Servicios de comercializacion" },
  { value: "80141600", label: "80141600 - Servicios de marketing" },
  { value: "80141601", label: "80141601 - Investigacion de mercados" },
  { value: "80141602", label: "80141602 - Servicios de marketing directo" },
  { value: "82101500", label: "82101500 - Servicios de publicidad" },
  { value: "82101501", label: "82101501 - Publicidad en medios impresos" },
  { value: "82101502", label: "82101502 - Publicidad en radio" },
  { value: "82101503", label: "82101503 - Publicidad en television" },
  { value: "82101504", label: "82101504 - Publicidad en internet" },
  { value: "82101600", label: "82101600 - Promocion de ventas" },
  { value: "82111700", label: "82111700 - Diseno grafico" },
  { value: "82111900", label: "82111900 - Servicios de fotografia" },

  // ── Servicios Contables y Financieros ──
  { value: "84101500", label: "84101500 - Servicios contables" },
  { value: "84101501", label: "84101501 - Contabilidad fiscal" },
  { value: "84101502", label: "84101502 - Servicios de auditoria" },
  { value: "84101503", label: "84101503 - Servicios de contabilidad de costos" },
  { value: "84101504", label: "84101504 - Teneduria de libros" },
  { value: "84101505", label: "84101505 - Preparacion de declaraciones de impuestos" },
  { value: "84101600", label: "84101600 - Servicios de credito" },
  { value: "84101700", label: "84101700 - Servicios de banca" },
  { value: "84111500", label: "84111500 - Servicios de seguros" },
  { value: "84111501", label: "84111501 - Seguros de vida" },
  { value: "84111502", label: "84111502 - Seguros de salud" },
  { value: "84111503", label: "84111503 - Seguros de automovil" },
  { value: "84111506", label: "84111506 - Servicios de agencia de seguros" },
  { value: "84121500", label: "84121500 - Servicios de banca de inversion" },
  { value: "84121600", label: "84121600 - Servicios de banca corporativa" },
  { value: "84131500", label: "84131500 - Servicios de nomina" },

  // ── Servicios Legales ──
  { value: "80121500", label: "80121500 - Servicios legales" },
  { value: "80121501", label: "80121501 - Servicios de derecho penal" },
  { value: "80121502", label: "80121502 - Servicios de derecho de familia" },
  { value: "80121503", label: "80121503 - Servicios de derecho laboral" },
  { value: "80121504", label: "80121504 - Servicios de derecho mercantil" },
  { value: "80121506", label: "80121506 - Servicios notariales" },
  { value: "80121600", label: "80121600 - Servicios de arbitraje y mediacion" },
  { value: "80121700", label: "80121700 - Servicios de patentes y marcas" },

  // ── Inmobiliario ──
  { value: "80131500", label: "80131500 - Servicios de arrendamiento de bienes raices" },
  { value: "80131501", label: "80131501 - Arrendamiento de oficinas" },
  { value: "80131502", label: "80131502 - Arrendamiento de viviendas" },
  { value: "80131503", label: "80131503 - Arrendamiento de edificios industriales" },
  { value: "80131504", label: "80131504 - Arrendamiento de locales comerciales" },
  { value: "80131600", label: "80131600 - Venta de bienes raices" },
  { value: "80131700", label: "80131700 - Servicios de administracion inmobiliaria" },
  { value: "80131800", label: "80131800 - Servicios de avaluos" },

  // ── Construccion ──
  { value: "72101500", label: "72101500 - Servicios de apoyo para la construccion" },
  { value: "72102900", label: "72102900 - Servicios de mantenimiento de edificios" },
  { value: "72111000", label: "72111000 - Servicios de construccion de edificios" },
  { value: "72121000", label: "72121000 - Construccion de carreteras y caminos" },
  { value: "72121400", label: "72121400 - Servicios de instalaciones electricas" },
  { value: "72121500", label: "72121500 - Servicios de plomeria" },
  { value: "72151500", label: "72151500 - Servicios de pintura e impermeabilizacion" },

  // ── Transporte y Logistica ──
  { value: "78101800", label: "78101800 - Servicios de transporte de carga" },
  { value: "78101801", label: "78101801 - Transporte de carga por carretera" },
  { value: "78101802", label: "78101802 - Transporte de carga aereo" },
  { value: "78101803", label: "78101803 - Transporte de carga maritimo" },
  { value: "78101804", label: "78101804 - Transporte de carga por ferrocarril" },
  { value: "78101900", label: "78101900 - Transporte de pasajeros" },
  { value: "78102200", label: "78102200 - Servicios postales y de mensajeria" },
  { value: "78111500", label: "78111500 - Alquiler de vehiculos" },
  { value: "78111800", label: "78111800 - Servicios de almacenaje" },
  { value: "78111803", label: "78111803 - Almacenaje en frio" },
  { value: "78121600", label: "78121600 - Servicios de empaque" },

  // ── Alimentos y Bebidas ──
  { value: "50000000", label: "50000000 - Alimentos, bebidas y tabaco" },
  { value: "50101700", label: "50101700 - Carne y aves de corral" },
  { value: "50112000", label: "50112000 - Leche y productos lacteos" },
  { value: "50131600", label: "50131600 - Chocolates y dulces" },
  { value: "50151500", label: "50151500 - Aceites y grasas comestibles" },
  { value: "50171500", label: "50171500 - Pan y galletas" },
  { value: "50192100", label: "50192100 - Bebidas no alcoholicas" },
  { value: "50202300", label: "50202300 - Bebidas alcoholicas" },
  { value: "90101500", label: "90101500 - Servicios de restaurantes" },
  { value: "90101600", label: "90101600 - Servicios de cafeterias" },
  { value: "90101700", label: "90101700 - Servicios de banquetes y catering" },

  // ── Salud y Medicina ──
  { value: "85101500", label: "85101500 - Servicios de salud" },
  { value: "85101501", label: "85101501 - Servicios hospitalarios" },
  { value: "85101502", label: "85101502 - Servicios de cirugia" },
  { value: "85101503", label: "85101503 - Servicios de consulta medica" },
  { value: "85101600", label: "85101600 - Servicios dentales" },
  { value: "85101700", label: "85101700 - Servicios de rehabilitacion" },
  { value: "85111500", label: "85111500 - Servicios farmaceuticos" },
  { value: "85121800", label: "85121800 - Servicios de laboratorio medico" },
  { value: "42000000", label: "42000000 - Equipo medico y de laboratorio" },

  // ── Educacion ──
  { value: "86101700", label: "86101700 - Educacion de adultos" },
  { value: "86101710", label: "86101710 - Servicios de capacitacion profesional" },
  { value: "86111600", label: "86111600 - Servicios de formacion profesional" },
  { value: "86111700", label: "86111700 - Servicios de ensenanza de idiomas" },
  { value: "86132000", label: "86132000 - Educacion y capacitacion a distancia" },
  { value: "86141500", label: "86141500 - Servicios de ensenanza artistica" },

  // ── Limpieza y Mantenimiento ──
  { value: "76101500", label: "76101500 - Servicios de limpieza de edificios" },
  { value: "76101501", label: "76101501 - Servicios de limpieza de oficinas" },
  { value: "76101502", label: "76101502 - Servicios de desinfeccion" },
  { value: "76111500", label: "76111500 - Servicios de control de plagas" },
  { value: "76121500", label: "76121500 - Servicios de recoleccion de desechos" },
  { value: "72101506", label: "72101506 - Servicios de jardineria" },

  // ── Seguridad ──
  { value: "92101500", label: "92101500 - Servicios de seguridad" },
  { value: "92101501", label: "92101501 - Servicios de guardias de seguridad" },
  { value: "92101502", label: "92101502 - Servicios de vigilancia" },
  { value: "92121700", label: "92121700 - Servicios de proteccion contra incendios" },
  { value: "46171500", label: "46171500 - Equipo de seguridad y vigilancia" },

  // ── Papeleria y Oficina ──
  { value: "44121600", label: "44121600 - Suministros de oficina" },
  { value: "44121700", label: "44121700 - Papel para impresion" },
  { value: "44121800", label: "44121800 - Papeleria" },
  { value: "44122000", label: "44122000 - Carpetas y archivadores" },
  { value: "56101500", label: "56101500 - Muebles de oficina" },
  { value: "56101504", label: "56101504 - Escritorios" },
  { value: "56101519", label: "56101519 - Sillas de oficina" },

  // ── Energia y Combustible ──
  { value: "15101500", label: "15101500 - Petroleo y destilados" },
  { value: "15101502", label: "15101502 - Gasolina" },
  { value: "15101504", label: "15101504 - Diesel" },
  { value: "15101506", label: "15101506 - Gas LP" },
  { value: "15121500", label: "15121500 - Gas natural" },
  { value: "83101800", label: "83101800 - Servicios electricos" },

  // ── Vehiculos y Refacciones ──
  { value: "25101500", label: "25101500 - Vehiculos de motor" },
  { value: "25101502", label: "25101502 - Automoviles o carros" },
  { value: "25101503", label: "25101503 - Camionetas" },
  { value: "25101900", label: "25101900 - Motocicletas" },
  { value: "25172500", label: "25172500 - Llantas" },
  { value: "25172504", label: "25172504 - Llantas para automoviles" },
  { value: "78181500", label: "78181500 - Mantenimiento y reparacion de vehiculos" },

  // ── Textiles y Ropa ──
  { value: "53101500", label: "53101500 - Ropa de hombre" },
  { value: "53101600", label: "53101600 - Ropa de mujer" },
  { value: "53102500", label: "53102500 - Uniformes" },
  { value: "53111600", label: "53111600 - Calzado" },

  // ── Agricultura ──
  { value: "10101500", label: "10101500 - Animales vivos" },
  { value: "10151500", label: "10151500 - Semillas y plantas" },
  { value: "10171500", label: "10171500 - Fertilizantes" },
  { value: "70111500", label: "70111500 - Servicios de cultivo" },
  { value: "70111700", label: "70111700 - Servicios de cosecha" },
  { value: "70121800", label: "70121800 - Servicios de cria de ganado" },

  // ── Eventos y Hospedaje ──
  { value: "80141900", label: "80141900 - Organizacion de ferias y eventos" },
  { value: "90101800", label: "90101800 - Servicios de bar" },
  { value: "90111500", label: "90111500 - Servicios de hoteles y alojamiento" },
  { value: "90111501", label: "90111501 - Hoteles" },
  { value: "90111502", label: "90111502 - Alojamiento temporal" },
  { value: "90151800", label: "90151800 - Servicios de viaje y turismo" },

  // ── Recursos Humanos y Personal ──
  { value: "80111500", label: "80111500 - Servicios de personal temporal" },
  { value: "80111600", label: "80111600 - Servicios de personal permanente" },
  { value: "80111700", label: "80111700 - Servicios de reclutamiento" },
  { value: "80111800", label: "80111800 - Administracion de personal subcontratado" },

  // ── Impresion y Diseno ──
  { value: "82121500", label: "82121500 - Servicios de impresion" },
  { value: "82121600", label: "82121600 - Servicios de grabado" },
  { value: "82121900", label: "82121900 - Servicios de encuadernacion" },
  { value: "55101500", label: "55101500 - Publicaciones impresas" },

  // ── Miscelaneos ──
  { value: "60101700", label: "60101700 - Libros" },
  { value: "14111500", label: "14111500 - Papel" },
  { value: "27111500", label: "27111500 - Herramientas manuales" },
  { value: "31162800", label: "31162800 - Tornillos y tuercas" },
  { value: "39121000", label: "39121000 - Cables electricos" },
  { value: "40141700", label: "40141700 - Tuberia y accesorios" },
  { value: "47131800", label: "47131800 - Productos de limpieza" },
  { value: "52161500", label: "52161500 - Electrodomesticos" },
  { value: "73152100", label: "73152100 - Servicios de produccion de video" },
];
