import json
import os

# ── File paths ────────────────────────────────────────────────────────────────
TOOL_RESULTS_DIR = (
    "/Users/jillydy/.claude/projects/"
    "-Users-jillydy/8f510acf-6f4c-4438-a9f7-31ff95715b04/tool-results"
)

FILE_NAMES = [
    "toolu_01QtZVbVMjHj9QRoeceNaKWm.json",
    "toolu_01B5gttQFCCnGgdHpyX1oWPT.json",
    "toolu_01QAbLxmngSAuUa85hbGkad3.json",
    "toolu_01Le83GKh6BsneGFiVakvMLg.json",
    "toolu_01PUKd2k8RgVMFjU4aQzcX2h.json",
    "toolu_017WZAt2fG1NdgA3aWpRUJLj.json",
    "toolu_01Ht5HwUsDj11aDLDdDLn1sJ.json",
    "toolu_01V3gDjtsQPmQr7tNnMagXaL.json",
    "toolu_01DKpj9sen9fLuFAMJ6g8AF8.json",
]

OUTPUT_PATH = (
    "/Users/jillydy/Library/Mobile Documents/com~apple~CloudDocs/"
    "Desktop/hs_companies.json"
)

# ── Owner map ─────────────────────────────────────────────────────────────────
OWNERS = {
    4650920: "Jovilyn Eissa Feh Cutiongco", 13470702: "Audrey Consul",
    13626201: "Karys Co", 15287709: "Patrick Gentry",
    15408634: "Alyssa Dela Cruz", 16607895: "Nix Eniego",
    16888201: "Bianca Chanelle Fallaria", 16989571: "Butch Manalo",
    16994861: "Vince Villa", 16994921: "Dave Cheever",
    16995091: "Bernice Locsin", 17014829: "Danica Alagon",
    17189661: "Lisanne Tumang", 17189681: "Leena Alumno",
    17280345: "Alexandria Gentry", 17636003: "Dennis Zabal",
    18012889: "Daryl Solis", 18013059: "Miszan Arce",
    18013094: "Joven Delos Santos", 18063184: "Owen Diamante",
    18063254: "Tiffany Mallillin", 18237231: "Liezl Marantal",
    18566582: "Dan Martin", 18566662: "Nastassja Natividad",
    18566797: "Gee Aligno", 18566867: "Inna Serio",
    18566892: "Sonia Lu", 18674497: "Earl Almonte",
    18739901: "Jane Andes", 18980694: "Dina Sorela",
    18980754: "Charm Pelobello", 19078512: "Sans Montecillo",
    19412392: "Dom De Castro", 19693322: "Nelsa Soliven",
    19693442: "Abegail Salo", 19693507: "Maria De Guzman",
    19696812: "Jeff Sumalde", 19696892: "JT Aaron",
    19696942: "Chris Torres", 19697052: "MJ Abuid",
    20023775: "Ernest Marsh", 21516055: "Jitka Contado",
    22057990: "VK Virata", 22748801: "Ivy de Ramos",
    22797784: "Jayson de Leon", 24878314: "Kelvin Araujo",
    25462650: "Charlotte Jimenea", 25717784: "Rachel Ching",
    26159381: "Erny Nazario", 26923991: "Jonalyn De Leon",
    29674577: "Jonalyn De Leon", 29885534: "Jane Villanueva",
    30239985: "Derrick Blanco", 30268594: "Marvin Dexter De Guzman",
    30465432: "JP Anatalio", 30560685: "Lizette Servanes",
    30831038: "Edward Musiak", 31060400: "Jed Go",
    31186253: "Chris Gamboa", 31186254: "Karen Benin",
    31306029: "Camille Morales", 31327886: "Nikki Ronessa Ladines",
    31351335: "David Valbuena", 31415703: "Charles Chua",
    31851691: "John Kevin Sebastian", 35179638: "Angel Pagulayan",
    35412030: "Jaypee Galo", 35412031: "Cassie Yusofi",
    35412032: "Rej Alvarez", 35412033: "Urim Hernandez",
    35412034: "Princeton Astorga", 35412035: "Angelito Rafols",
    35412108: "Donn Panlilio", 35412109: "Cha Mamuyac",
    35412110: "Sheila Nicolas", 35412111: "Crystel Jane Insigne-Ambrocio",
    35412112: "john jay garfin", 35412113: "Mary Kay Docto",
    35412180: "Amiel Dominic Alvizo", 35412290: "Danielle Maximo",
    35875209: "Chendee Ancheta", 36690222: "Urk Acapulco",
    37453874: "deborah de beer", 37454014: "Karofa Kristine Cartano",
    37454015: "Jeanine Alexis Cabalquinto", 37552104: "Billy Reyes",
    37552131: "Jennifer Coca", 37552134: "Ethan Laud",
    37710122: "Rocky Gaspar", 37784366: "Erik de Leon",
    37959577: "Charlene Cunanan", 38205895: "Oniedia dela Cruz",
    38209200: "Adoracion Roxas", 38209212: "Xeena Paredes",
    38504289: "Catherine Dimacali", 38546749: "Julian Brien",
    38546750: "Mic Ganoy", 38546751: "Irma Perey",
    38546752: "Jeneva Dano", 38546848: "Luigi Beltran",
    38546849: "Louie Ballesteros", 38546851: "Mafe Ecot",
    38597410: "Ralph Embalsado", 38665234: "Richard Sy",
    38790531: "Adrian Rodriguez", 38790536: "Ariane Dizon",
    38790537: "Khristine Bernardo", 38790538: "Lawrence Mendoza",
    38790539: "Riezhel Punzalan", 38790544: "Timothy Valdeavilla",
    38918656: "Julie Martinez", 38918658: "Charlotte Jimenea",
    39075200: "Lea Pastrana-Almiranez", 39075201: "Patricia Tejada",
    39075409: "Armee Gale Hayag", 39075410: "Dhiren Dhanani",
    39075411: "Daisy Torres", 39075415: "Samantha Garcia",
    39131475: "Hanna Equipaje", 39131477: "Lester Aguirre",
    39131480: "Romnick Sausa", 39131630: "Chino Cruz",
    39134512: "Clarenz Casal", 39134517: "Oliver Velasco",
    39193529: "Jed Gamir", 39193533: "Jay-Di Francisco",
    39300940: "Carl Joshua Garcia", 39322043: "Kyle Imperio",
    39322048: "Michael Tan", 39322271: "Katryn Angela Saldajeno",
    39322272: "Miguel Mapua", 39322277: "Ken Zaide",
    39406559: "Chris Ureta", 39406561: "Sheryl Lagura",
    39428887: "Emy Figueroa", 39428994: "Ruby Nabiula",
    39428995: "Mac Pua", 39429006: "Ged Batallones",
    39429090: "Gia San Juan", 39609340: "Jim Espinosa",
    39609343: "Danielle Casaje", 39609348: "Joliel Gabasa",
    39609391: "Roberto Ramorez", 39609396: "Francis Bucao",
    39609399: "Rafa Ticzon", 39893402: "Gabriel Lorenzo Cadena",
    39893605: "Wilson Astorga", 39893621: "John Teologo",
    39893633: "Eugene Natividad", 39893663: "Shaira Lyn Abdon",
    39898692: "Jesthin Josel Velasco", 39983882: "Kirk Davies Reyes",
    40149000: "Robelyn Collamar", 40149001: "Isabela Cabreros",
    40149002: "Donna Cruz", 40149038: "Jo Veloria",
    40149108: "Patrice Chantal Chan", 40149109: "Lester Mercado",
    40203728: "Eduardo Gutierrez", 40239691: "Ricardo Rigodon",
    40486591: "Christine Garcia-Soriano", 40486595: "Abigail Neri",
    40491071: "Allyssa Ruazol", 40491090: "Kaye Flores",
    40491091: "Jeramie Antier", 40491123: "Jeramie Antier",
    40493314: "Miren Eizmendi", 40751395: "Derek Albanese",
    40903739: "Grace Vivero", 40903743: "Lyka Lotino",
    41248184: "Sprout Insight", 41935379: "Joan Tafalla",
    41935534: "Andrea Quimson", 42045797: "Soc Orlina",
    42358891: "lester mercado", 42726171: "Nitzan Mazor",
    43275725: "Arlene De Castro", 43342287: "John Lemuel Linga",
    44416908: "Brain Gregorio", 44416980: "Ceejay Gomez",
    44416983: "Mary Ann Anyayahan", 44574180: "Client Ops Team",
    44608300: "Juan Miguel Bayani", 44649530: "SDR Master Pool",
    44730799: "Gianfrancesco Nery", 44788159: "Princeton Astorga",
    44788211: "Beverly Quion", 44788216: "Lester Ople",
    44788319: "Jolo Yulo", 44788324: "Ronald Nino Obach",
    44788375: "Jay-Ryan Trinidad", 44895692: "Implementation Team",
    44895877: "Finance Team", 44996208: "Sachiko Zorrilla",
    44996282: "Keiji Makita", 44996292: "Dennice Madrid",
    44996296: "Jullie Ann Lim", 45045478: "Samantha Kaye Avestruz",
    45098190: "Lyra Santarina", 45318986: "Sherikka Nakamura",
    46352877: "Ma Jerona Salve Casabuena", 46352880: "Marvin Lumasac",
    46352981: "Gab Llanto", 46352993: "Jerrome Lusung",
    46352997: "Elaine Santos", 46354171: "Gab Llanto",
    46809724: "Sanjay Belani", 46998338: "Lexi Roxas",
    46998451: "Sharina Mariano", 46998653: "Jum Picar",
    47047944: "CSM Team", 47274422: "Presales Team",
    47374185: "Cristina Tabag", 47561592: "Richard Keith III Reyes",
    47735304: "Alvin Dela Cruz", 47808673: "Joe Mari Salaver",
    47901945: "Liz Lacandazo", 48098296: "Janine Hilis",
    48098494: "AJ Salazar", 48098515: "Josephine De Joya",
    48098533: "Reynard Corpuz", 48104582: "Abigail Hipolito",
    48106771: "Karen Mocling", 48229378: "Sales Management Team",
    48260344: "Jelice Del Rosario", 49209539: "Nino Jeetom Hilario Pitogo",
    49563062: "Product Design", 49868107: "Arianne Ong",
    50150374: "Daisy Batislaong", 50280706: "Mikhail Anthony Reano",
    50990663: "Gaby Fonseca", 51467034: "Angelica Fernandez",
    51467035: "Patrice Lamo", 51467036: "Kharla Glorioso",
    51467281: "Ed Wagner Alquiros", 51467282: "Jean Alessi Dulay",
    51467287: "Abbygail Sumaylo", 51589519: "Kislay Chandra",
    52262708: "Nikki Godoy", 53779614: "Luis Lorenzo Sugay",
    54440927: "cristopher aquino", 54441093: "Krishen Pauline Santos",
    54441382: "Sylvester Casas", 54637664: "Edwin Balajo",
    54637669: "EZEKIEL CUSTODIO", 54637677: "Geoffrey Ogang",
    54637681: "Maria Carmina Ramos", 54637825: "Arj De Jesus",
    55535073: "Osheri Fima", 55985675: "Dwight Calucag",
    57085899: "Carl Arwen Torres", 57415808: "Keara Eugenio",
    57499243: "Angeline Riboroso", 58253457: "Razor Bucatcat",
    58254036: "Bryan Gabriel Tiu", 58343602: "Cherry Anne Lavina Almajose",
    58343607: "Louie Picar", 58344623: "Luis Jose Santos",
    59246828: "Hans Dieter Comagon", 61585602: "Sissada Siripongsaroj",
    62030050: "Greatchen Dee Ancheta", 63443869: "Samm Tong",
    63443871: "Mylene Cuevas", 64459827: "Adi Salvatierra",
    64686880: "Rexelle Estacio", 67282778: "Grace Aquino",
    67712002: "Maryniel Odin", 67712670: "Gwyn Contreras",
    71736411: "Peter Louise Garnace", 73525625: "Angeline Flores",
    75541507: "Michelle Dungog", 75901987: "Armie Villafuerte",
    75901988: "Christel Angel Factor", 75901989: "Denise Gonowon",
    75902370: "Zona Rocelle Merto", 75902371: "Paula Angila Vaflor",
    76082260: "Ferds Guasque", 76082261: "John Ronquillo",
    76158123: "Nicole Faustino", 76282779: "Hazel Anne Ortiz",
    76531137: "Aira Mae Arquillo", 76754501: "Gemiliano Jay Calangi",
    77029377: "Charenejane Eursurattanachai", 77032828: "Paul John Domingo",
    77034472: "Niccolo Tioseco", 77071514: "Karissa Verayo",
    77071637: "Mukesh Jagwani", 77072587: "Java Gancayco",
    77532397: "Ma. Elen Obligar", 77532398: "Kei Milleni Regen",
    77532399: "Paul Angelo De La Cruz", 77532400: "Anna Marie Magallanes",
    77532401: "Jasmine Faye Danganan", 77747547: "Rolando Ebao",
    77920334: "Product Managers", 78004577: "Mesiya Panya",
    78006003: "Ryan Pulido", 78043167: "Christian Jonell Mercado",
    78138686: "Gem Sucaldito", 78190467: "Ross Benedict Palileo",
    78283673: "Reine Suarez", 78365408: "Ramona Jazmine Ching",
    78594701: "Zaccharina Celis", 78594702: "Sophia Roxas",
    78594703: "Lara Jill Guadalupe", 78594704: "Deniela Cyrille Suarez",
    78594705: "Mark Anthony Gelig", 78594706: "Krissen Hay De Ocampo",
    79183468: "John Joshua Male", 79293413: "Lorbel Cachero",
    79293414: "Robby Oliver Mendoza", 79293415: "Cielo Migie Ilagan",
    79293416: "Trisha Villegas", 79293417: "Marc Lorence Parrosa",
    79293418: "danna gatchalian", 79293419: "Cecile Velasco",
    79352068: "Jose Fernando Salvosa", 79352069: "Rachelle Serneo",
    79355449: "Solution Services", 79383581: "Xerjgei Advincula",
    79567565: "Sprout Support Team", 79886729: "Andrea Gaor",
    79945545: "Brian Dominic Azarcon", 80239810: "Bryan Nunez",
    80244245: "Jerome Portera", 80244507: "Marcel Pizarras",
    80295421: "Paul Ryan Arcolas", 80297730: "Christianne Natividad",
    80298375: "Justin Bernabe", 80760581: "Aryanna Manalastas",
    80791125: "Abegail Cruz", 80791745: "Pam Dajalos",
    80792292: "Pamela Mae Furio", 80848050: "Doungkamol Chanaboon",
    81000809: "Raymond Cruzin", 81124710: "Anton Santiago",
    81508314: "Ma. Carissa Guevarra", 81508315: "Charlene Verzosa",
    81508316: "Lester Recto", 81508317: "Lorrens Anne Villaruz",
    81601823: "Ana Mari Battung", 81621447: "John Paulo Ligad",
    81621578: "Jessiel Ann De Guzman", 81622027: "Katrina Blanca Catalan",
    81801977: "Nicole Maniego", 81959420: "Arjohn Romero",
    82157577: "DR Villrec Omawas", 82157634: "Rona Mae Pablo",
    82157642: "Valjomel Moya", 82178475: "John Ronald Lopez",
    82194724: "Phongsakorn Bangsomboon", 82454089: "Jaden Marek Yu",
    82454147: "Rafael Christopher Serapio", 82554751: "Sprout Billings",
    82581457: "Jill Coleen Panlilio", 82776341: "ynna navarra",
    83035604: "Jacy San Luis", 84006918: "Crystal Dana Pike",
    84387404: "Nonglak Mayteekraingkrai", 84394942: "Firdaus Ibrahim",
    84985551: "Dianara Dionisio", 85352608: "Kristoffer Vincenzo Vega",
    85352612: "Samirah Khattab", 85355107: "Katrina Papa",
    85592706: "Patricia Lopez", 85760131: "Aristides Bejosano",
    86091156: "Lawrence Ralph Bachini", 86127620: "Moises Salazar",
    86129552: "Customer Advocacy Team", 87343647: "Jessalyn Cerdanio",
    87343648: "Darrell John Suficiencia", 87382660: "Bea Punzalan",
    88125278: "Vk Virata", 88321046: "Janyl Tamayo",
    88426271: "Pornpan Buasunthorn", 88531942: "Anielyn Nepomuceno",
    88567735: "Roanne Gonzales", 88614882: "Paramaporn Malaitong",
    88616608: "Cedrick John Darro", 88827348: "Jeferson Mari",
    89816717: "Carla Gonzales", 89816731: "Roberto Cezar Latonio",
    92015932: "Lorenzo Miguel Macapagal", 92024744: "JENNICHA TANTEO",
    92807766: "Mari Ann Therese Paling", 92823446: "Jayster Kieth Guce",
    95471540: "Chedelle Fatima Florido", 96572537: "Ian Mauro Timbang",
    96572600: "Enzo De Leon", 96572685: "Paolo Bhatia",
    96572691: "Jhon Melky Chumacera", 98477842: "Jerson Paul Iglesias",
    99570284: "Bernadette Catalan", 99572271: "Anne Quijano",
    99594057: "Alcel Potayre", 101537342: "Mary Elizabeth Reantaso",
    104872227: "Heather Sarona", 105953042: "Judyllynd Castillo",
    106399390: "Marianne Reyes", 109887929: "Mark Johnson",
    109890388: "Nicole Pallesgon", 109907331: "Jillian Mozelle Factora",
    110149787: "Rose Ann Amul", 112183828: "Gilbert George Siapno",
    113199447: "Crissy Partosa", 113204909: "Ericka Tomas",
    113536655: "Bryan Paul Inocencio", 117927347: "Ken Regis",
    119208779: "Dorothy Estrella", 119781233: "Jessica Orinday",
    120027306: "Mareon Jason Patrick Ocan", 126788392: "Myra Mercurio",
    127676475: "Bela Cortez", 127690888: "Cheslyn Gamalong",
    130010391: "Patricia Barruela", 135437234: "Beverly Arcino",
    135439989: "Myrose Ramones", 135439990: "Princess Almoradie",
    135439991: "Michelle Angela Ferrer", 137058651: "Paul Lorenz Yusingco",
    140573282: "Thea-Ar Keith Torres", 140573283: "Nelson Cabero",
    140575814: "Luigi Jimenez", 140575815: "Joshua Ponce",
    140575816: "C Jhay Azores", 140900149: "Lorenz Coleen Reyes",
    141822581: "Crystel-Joy Tamon", 146277268: "Kathryn Ann Manuel",
    147106438: "Renzo Belardo", 150048270: "Sarah Medilo",
    150048271: "Ley Castillo", 150952990: "Roselyn Banila",
    150952991: "Jay-R Osma", 150955705: "Jessy Lora Diaz",
    150955776: "Aletha Dela Cruz", 153275447: "Charmaine Perillo",
    153926544: "Jennefer Cases", 153926573: "Rabi Javier",
    153972383: "Yvaniel Alinsunurin", 155576667: "Paula Yap",
    155579715: "Jaime Augusto Silpedes", 155579716: "Angelica Romasanta",
    155579717: "Jessica Irish Dela Cruz", 156232273: "Fritz Roma",
    159029251: "Jaevy John Balagot", 159029252: "Arianne May Salunga",
    159029253: "Clark Bitancor", 159029254: "Miguel Misa",
    159029255: "Criselle Vergara", 161259534: "Charly Andres",
    165754038: "Ana Panares", 172223912: "Johnna Villanueva",
    172223913: "Kaye Anne Lo", 174124945: "Vk Virata",
    183936783: "Jean Carry Batulan", 183936892: "Yzabella Ylagan",
    183936893: "Diana Marie Glorioso", 184754066: "Kate Potian - Janairo",
    184818557: "Chloe Santiago", 186528930: "Alicia Alves",
    186528931: "Aldwin Baliguas", 187262114: "Fernand Noel Ramos",
    187262115: "Mia Cancio", 191775546: "Ma. Chelsea Rodriguez",
    192992136: "Reyam Paul Carias", 192996169: "Anthony Dihiansan",
    194887709: "Your Sprout Consultant", 194890368: "Fahad Taib",
    198077332: "Ayesa Parreno-Solido", 203077183: "Psydi Mae Oatemar",
    203815012: "Jean Marjhorie Liquigan", 205939274: "Gabriel Lorenzo Cadena",
    207221364: "dianne pomento", 213355428: "Kimberly Virina",
    218975585: "Timothy Glenn Walden Morales", 219003178: "Xia Domingo",
    220721650: "Aloicius Justine Kochensparger", 222060561: "Almira Mara Tuguigui",
    222060562: "Arnie Mae Baltazar", 225698846: "Daniel Mangahas",
    225699483: "Angela Velas", 225702562: "Rizzalyn Morada - Berce",
    227324308: "Chrisha Elba Abrenica", 228175431: "Ohly Villegas",
    230127025: "Glenda Sevilla", 230837041: "Keven John Tribunalo",
    230837087: "Catherine Bodino", 231311789: "Lemuel Teh",
    231354496: "Myra Abad", 231376518: "Emil Sanchez",
    231761485: "Krystel Maano", 232993813: "Frances Mae Penaroyo",
    236133259: "Gerald Acosta", 236136757: "Maureen Quirante",
    236136758: "Mark Anthony Cuasito", 236647060: "Bianca Marie Pecson",
    240238113: "Revenue Operations", 242980193: "Carrie Anika Carbo",
    244499847: "Kimmy Domingo", 244582175: "Julius Sayseng",
    247124225: "Juan Diego Canezo", 248060532: "Fiona Nicolas Gurtiza",
    248073504: "Von Martino", 251301081: "France Paredes",
    251614641: "Jean Christianne Semilla", 252139904: "Miguel Lorenzo Singian",
    252177005: "Frince Badion", 252340278: "Rita Pascual",
    254486119: "Marie Christine Espineda", 257553813: "Julianne Manuel",
    259739806: "Jacqueline Gilbuena", 262323213: "Noel Gonzales",
    262603320: "Audi Abas", 265724442: "Kit Sumabat",
    266538016: "Myla Hernandez", 268682071: "Maria Elaine Tarca",
    268843168: "Kim Dalisay", 270739236: "Billy Jean Dungo",
    270740102: "Ma. Ana Saavedra", 272607212: "Iras Naga",
    278612886: "Jolina Ocampo", 278706991: "Sarah Ramos",
    278706992: "Cristy Mae Mendoza", 279529832: "Stephen Joseph Apolonio",
    283022761: "Rommel Batalla", 285347846: "Alyssa Belmonte",
    289665140: "Javier Lopez", 289665337: "Ricardo Rigodon",
    290302531: "Nathaniel Yatco", 302648282: "Andrew Joseph Anlap",
    303571204: "Majurie Fernandez Bucay", 303714456: "Jessica De Paz",
    303769108: "Andre Raneses", 303774221: "Jocelyn dela Cruz",
    308633423: "Jazzmin Disuanco", 319711272: "Rex Russell Colina",
    321297592: "Jerry San Pedro", 326887459: "Kenjiva Quiano",
    326892383: "Roxon Dizon", 326892438: "Rowena Florencio",
    331214879: "EJ Garcia", 331990895: "John Marie Lema",
    337642877: "Florence Rayala", 337646451: "Isabel Carmina Marzo",
    337646700: "Maureen Santos", 339960234: "Renalyn Lacsamana",
    342390622: "Melvin Rabadon", 342647572: "Janrick De Jesus",
    342647716: "Herbert David Salvaleon", 342805335: "Nikaella Therese Vega",
    343560111: "Mabel Duyo", 348918097: "Jamie Rosseditt Garcesa",
    350870331: "Dom Umandap", 351843752: "Ramon Jose Rayos",
    354967044: "Nowell Batoon", 354967045: "Michael Paul Yalung",
    361273163: "Blessy Mae Serbana", 361278380: "Aljie Godoy Sta. Maria",
    361278381: "Michael Atanacio", 361278382: "Mary Lano",
    361424189: "Karen Kate Lampano", 361424190: "Darrel Cabarrubias",
    361424391: "Jackqueline Salvador", 362898323: "Wil Luna",
    368312674: "Kurt Ang", 370076915: "Product Fintech",
    371980646: "Eunice Mendoza", 378363806: "James Lucas",
    379370147: "Robert De Castro", 383768323: "Xavier Salera",
    384392846: "Leilanie Jean Urbina", 384400415: "Allan San Juan",
    396510461: "Ana Calubad", 396579952: "Louie Anthony Lazaro See",
    397521427: "Mike San Pascual", 401204398: "Agno Virgilio Almario",
    407792544: "Camille Guangco", 407792545: "Zaren Endegado",
    407792666: "Leslie Alonzo", 407792667: "Djiether Ann Manansala",
    408855196: "Debie Giron", 411592978: "Hannah Grace Mendoza",
    415289900: "Nia Maranan", 418320300: "Sheilene Marie De los Santos",
    418464520: "Nadine Sebastian", 418464889: "Camille Bayan",
    421451871: "Lance Gabriel Torres", 429727068: "Amity Rose Lim",
    431851051: "Mat Galuego", 431851052: "Lana Pineda",
    440665952: "Louise Nicole Miller", 446580740: "Richard Perry",
    452903855: "Jorrayne Manalac", 459667482: "Issa Aviles",
    459667483: "Azelle Lee-Flores", 464588862: "Erika Michelle Aparte",
    472986398: "Jarinee Punpeang", 474211675: "F Pena",
    474217623: "Dominique Ann Philomena Lacuna", 474217624: "Samantha Wong",
    476099606: "Jill B. Diaz", 476104201: "Kathleen Lacambra",
    477338808: "John Timothy Sy", 477344835: "Arni Acosta",
    477346449: "Lea Carillo", 479620131: "Katrina Mae Miranda",
    480877206: "Mathew Quiazon", 489161885: "Julian Carlo Calilao",
    489162044: "Kimberly Mae Orjaleza", 490120204: "Raymond Suriaga",
    490120205: "Daphane Flores", 491475551: "John Lance Salazar",
    495768490: "Jose Fuliga", 497744262: "Samantha Taguibao",
    503356633: "Joseph Indolos", 504978060: "Shen Haig",
    504978176: "Ryan Geronimo", 504982443: "Javier Roberto Villavicencio",
    504982607: "Chris U", 508624310: "Jean Marcus Laxa",
    508712491: "Chaze Eurika Martinez", 508739466: "Kristel Joy Triveles",
    508739467: "Shiela Marie Landicho", 508746624: "Lew Riva",
    514486967: "Maria Theresa Velasco", 515181057: "Pornpimon Pipatsaowapong",
    519800674: "Data Science", 521161639: "Nayomi Dane Abobo",
    526588504: "Demcy Charles Cachero", 528217930: "Aldrin Christian Balla",
    528218030: "Angelo Nico Ravilas", 529876869: "Paolo Suarez",
    534743727: "Louie Francia", 534743728: "Sofia Cimeni",
    537122193: "Alyssa Gregorio", 539036047: "Rogelio Huilar",
    539036048: "Paul John Pical", 539091992: "Jown Eusebio",
    539330641: "Blaise Brandon Solis Cosico", 539330642: "Jaypee Cuyugan",
    553289243: "Takayuki Kenzo Aman", 559834418: "Johanna Brillantes",
    562904025: "Rovilyn Palco", 566333561: "Teki Repalda",
    566333562: "John Anthony Los Banos", 566340190: "Noel Duran",
    568997028: "Demand Gen Team Sprout", 571093618: "Ged Batallones",
    571093662: "Carlo Arias", 583336468: "Noel Lorenzo Vicente",
    587026099: "Grezaldy Jose Jr. Nacionales", 587026101: "Yvonne Edmanoel Cruz",
    587078767: "Anthony Obanil", 587202172: "Neilo Mari Santos",
    592956499: "Amit Pachaury", 597068674: "Miriam Pulido",
    600431694: "Alyssa Andrea Salinas", 609231157: "Ma. Rexelle Estacio",
    616833626: "Marjorie Manio", 628794399: "Patricia Mercado",
    633883776: "Janessa Ira Carlos", 634519299: "Alexandra Marie Dela Cruz",
    636390422: "Dylan Wong", 644305720: "Marketing Team Sprout",
    644305721: "Events Sprout", 644305722: "CS Team",
    645436551: "Ernel John Joaquinne Gonzaga", 645439493: "Christine Garcia",
    647790691: "Christian Joseph Flores", 649012257: "Clarisse Bautista",
    649012258: "Natalya Patolot", 658561134: "Aubrey Celestial",
    658635942: "Sales Team", 673203081: "rancel reynoso",
    674425366: "Mitzi Molina", 674545849: "Mark Ian Balibagoso",
    679594892: "Gian Paulo dela Rama", 688142977: "Gabriel Cristobal",
    688553989: "Rica Paula Belita", 691144826: "Mark Paolo Flores",
    692423433: "Jethro Jesse James Jamelo", 692423434: "Ellinor Ferriol",
    696082667: "Kevin Meneses", 700769179: "Matthew Abellaneda",
    717138258: "Jemmabel Fajardo", 724398404: "Vince Villamil",
    733328483: "Henekein Afable", 733328704: "ryan ochavillo",
    733328810: "Saldy Juanico", 733328982: "Leslie Agat",
    733335156: "Gerard Poblete", 738818912: "Mikhaela Angela Batara",
    738951196: "Roxanne Areja", 739126176: "Jaisel Merin",
    748479353: "Cookie Enriquez", 751512148: "Betty Margulies",
    752736666: "Rhea Reanoga", 789807150: "Miguel Jaime Porta",
    803549924: "Ma. Angelica Guerrero Santos", 805742719: "juneth baniqued",
    831053802: "JC Bungay", 837633722: "Ryan Fornoles",
    869444941: "Kenta Ueda", 938366531: "Charisse Ann Insigne",
    951440626: "Sirirat (Katie) Phrompraphun", 964468653: "Princess Ella",
    965562125: "Nerida Lindsay", 978264391: "Marlon Montecerin",
    1012019198: "Diana Vivo", 1026598649: "April Guiquing",
    1033097161: "Vannaporn Aeh", 1067436892: "Joanna Grace Tolentino",
    1109880428: "Lucky Lyne Penalosa", 1129404207: "Alliance Success Management",
    1134757843: "Roxanne Dominique Ulita", 1154453474: "Angelica Ignacio",
    1190137479: "Jonathan Joson", 1201040952: "Rachel Joy Camelotes",
    1236963447: "Abi Magalona", 1256267073: "Tor Prommas",
    1257523848: "Chatinee (Nada) Meewong", 1263977666: "Chakkree Champhot",
    1266483965: "Paola Therese Ranola", 1275771134: "Mary Jane Dela Cruz",
    1322100373: "Arol Magtalas", 1340034430: "Jennifer Villamor",
    1362046170: "Fredrick Bermudez", 1365552762: "Your Sprout TH Consultant",
    1381001831: "Jeasry Kate Mamac", 1402170346: "Janine Kau",
    1425191422: "Kin Pago Olahay", 1449153926: "Akisha Abella",
    1460307713: "Denise Bogarin", 1471540436: "Apicha (Pat) Panprateep",
    1483228903: "Robert Horgan", 1489820695: "Martin Dizon",
    1498235916: "AJ Araneta", 1522680719: "Artittaya Ubonnuch",
    1532448824: "Dan Averilla", 1539109967: "Moses Ojera",
    1549865716: "Thanakorn Suwannakronrat", 1557084630: "Kris Zbikowski",
    1601620305: "Sage", 1614158359: "Maureen Gail Frisco",
    1614256539: "Melanie Magana", 1621945549: "Lore Rodriguez",
    1635393673: "Clydell Jane Cabarle", 1649141916: "Janica Aldana",
    1649498458: "Jay Mark Balason", 1662845489: "Ira Leigh Sevilla",
    1685714189: "Mykie Marie Mangahas", 1700291327: "Ernest Joni Tabada Ejay",
    1702783815: "Thea Trillanes", 1734273762: "Gianina Beatrice Quezada",
    1783819240: "Alyssa Arenas", 1902631646: "Boonsom Khuntong",
    1904457177: "Sirirat (Praew) Rattanapongpan", 1914439518: "Therese Madlangbayan",
    1932243419: "Abreal Cunanan", 1954420064: "Marc Joseph Tolentino",
    1966709437: "Joanna Campo", 1974072453: "AJ Benederio",
    2027078404: "Jan Michael Tibayan", 2031515381: "Gio Buenvenida",
    2058357739: "Joanna Marie Marquez", 2063762345: "Oan - Prakartkiet Sirion",
    2134679214: "Julien Zoma",
}

# ── Parse helper ──────────────────────────────────────────────────────────────
def normalize_netsuite_id(raw):
    """Strip trailing '.0' if the remainder is purely digits."""
    if raw and raw.endswith(".0"):
        candidate = raw[:-2]
        if candidate.lstrip("-").isdigit():
            return candidate
    return raw or ""


def parse_tool_file(filepath):
    """Return list of company dicts from one tool-result JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        outer = json.load(f)

    # outer is a list; first element has "text" key with the HS API JSON string
    inner_text = outer[0]["text"]
    inner = json.loads(inner_text)

    results = inner.get("results", [])
    page_total = inner.get("total", None)
    return results, page_total


# ── Main ──────────────────────────────────────────────────────────────────────
all_companies = []
grand_total_reported = None

for fname in FILE_NAMES:
    fpath = os.path.join(TOOL_RESULTS_DIR, fname)
    if not os.path.exists(fpath):
        print(f"WARNING: file not found: {fpath}")
        continue
    results, page_total = parse_tool_file(fpath)
    if grand_total_reported is None and page_total is not None:
        grand_total_reported = page_total
    print(f"  {fname}: {len(results)} companies (page total reported: {page_total})")
    all_companies.extend(results)

# ── Check for potential missing page 9 (offset 1600) ─────────────────────────
if grand_total_reported is not None and len(all_companies) < 1680:
    print(
        f"\nWARNING: Only {len(all_companies)} companies loaded, but total reported "
        f"is {grand_total_reported}. Page at offset 1600 may be missing."
    )

# ── Build output records ──────────────────────────────────────────────────────
output = []
for result in all_companies:
    props = result.get("properties", {})
    hubspot_id = str(result["id"])
    raw_ns = props.get("netsuite_id", "") or ""
    netsuite_id = normalize_netsuite_id(raw_ns)
    company_name = props.get("name", "") or ""
    hubspot_owner_id = props.get("hubspot_owner_id", "") or ""

    if hubspot_owner_id:
        try:
            owner_name = OWNERS.get(int(float(hubspot_owner_id)), "")
        except (ValueError, TypeError):
            owner_name = ""
    else:
        owner_name = ""

    output.append(
        {
            "hubspot_id": hubspot_id,
            "netsuite_id": netsuite_id,
            "company_name": company_name,
            "hubspot_owner_id": hubspot_owner_id,
            "owner_name": owner_name,
        }
    )

# ── Write output ──────────────────────────────────────────────────────────────
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# ── Stats ─────────────────────────────────────────────────────────────────────
total = len(output)
with_owner = sum(1 for c in output if c["owner_name"])
print(f"\nTotal companies processed : {total}")
print(f"Companies with owner name : {with_owner}")

# Spot checks
for needle, label in [("SagaEvents", "SagaEvents"), ("Knack Global", "Knack Global")]:
    matches = [c for c in output if needle.lower() in c["company_name"].lower()]
    if matches:
        for m in matches:
            print(f"Spot check [{label}]: '{m['company_name']}' -> owner_name = '{m['owner_name']}'")
    else:
        print(f"Spot check [{label}]: NOT FOUND")

print(f"\nOutput written to: {OUTPUT_PATH}")
