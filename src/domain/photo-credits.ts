/*
 * Créditos de las fotografías.
 *
 * Las imágenes del sitio son de terceros y están publicadas bajo licencias
 * Creative Commons. Esas licencias permiten usarlas y modificarlas —acá se
 * reescalaron y recortaron— a cambio de una sola obligación: nombrar al autor y
 * la licencia. Eso es lo que hace esta lista.
 *
 * Va en una página aparte y no encima de cada foto porque atribuir no es lo mismo
 * que poner un cartel de advertencia sobre la imagen: cumple igual y no estorba la
 * lectura del sitio.
 *
 * Las fotos ilustran proyectos inventados y no corresponden a los lugares que el
 * sitio nombra; los términos de uso lo dicen.
 */

export interface CreditoFoto {
  archivo: string;
  titulo: string;
  autor: string;
  licencia: string;
  origen: string;
}

export const URL_LICENCIAS: Record<string, string> = {
  BY: 'https://creativecommons.org/licenses/by/2.0/',
  'BY-SA': 'https://creativecommons.org/licenses/by-sa/4.0/',
  CC0: 'https://creativecommons.org/publicdomain/zero/1.0/',
  PDM: 'https://creativecommons.org/publicdomain/mark/1.0/',
};

export const CREDITOS: CreditoFoto[] = [
  {
    archivo: 'altos-de-panguilemu-1.jpg',
    titulo: 'J. Lohr Arroyo Seco Vineyard Rows',
    autor: 'Danicox40',
    licencia: 'BY-SA',
    origen: 'https://commons.wikimedia.org/w/index.php?curid=116740428',
  },
  {
    archivo: 'altos-de-panguilemu-2.jpg',
    titulo: 'Brightening',
    autor: 'Nicholas_T',
    licencia: 'BY',
    origen: 'https://www.flickr.com/photos/14922165@N00/293413649',
  },
  {
    archivo: 'vega-alegre-iii-1.jpg',
    titulo: 'Aerial View of Farmland',
    autor: 'earth_photos',
    licencia: 'BY',
    origen: 'https://www.flickr.com/photos/41078423@N00/79668034',
  },
  {
    archivo: 'vega-alegre-iii-2.jpg',
    titulo: 'The young ones',
    autor: 'zenera',
    licencia: 'BY-SA',
    origen: 'https://www.flickr.com/photos/35237098471@N01/29656965',
  },
  {
    archivo: 'lomas-de-cauquenes-1.jpg',
    titulo: 'Astfeld #1',
    autor: 'josef.stuefer',
    licencia: 'BY',
    origen: 'https://www.flickr.com/photos/20375052@N00/6590610',
  },
  {
    archivo: 'lomas-de-cauquenes-2.jpg',
    titulo: 'House',
    autor: 'midiman',
    licencia: 'BY',
    origen: 'https://www.flickr.com/photos/41611970@N00/306765625',
  },
  {
    archivo: 'barrio-los-robles-1.jpg',
    titulo:
      "New houses being built, Sayer's Crescent, Wisbech St Mary - 13 - geograph.org.uk - 4930887",
    autor: 'Richard Humphrey',
    licencia: 'BY-SA',
    origen: 'https://commons.wikimedia.org/w/index.php?curid=133100547',
  },
  {
    archivo: 'barrio-los-robles-2.jpg',
    titulo: 'A house construction site',
    autor: 'hsivonen',
    licencia: 'BY',
    origen: 'https://www.flickr.com/photos/39049383@N00/190946274',
  },
  {
    archivo: 'mirador-del-maule-1.jpg',
    titulo: 'New residential tower, East Boston, 2017 P1010855',
    autor: 'NewtonCourt',
    licencia: 'BY-SA',
    origen: 'https://commons.wikimedia.org/w/index.php?curid=62338519',
  },
  {
    archivo: 'quebrada-honda-1.jpg',
    titulo: 'Green, Green Grass Of Home',
    autor: 'zenera',
    licencia: 'BY-SA',
    origen: 'https://www.flickr.com/photos/35237098471@N01/252449343',
  },
  {
    archivo: 'quebrada-honda-2.jpg',
    titulo: 'Bat-eared foxes',
    autor: 'Wildcat Dunny',
    licencia: 'BY',
    origen: 'https://www.flickr.com/photos/88837718@N00/87670475',
  },
];

export default CREDITOS;
