// Génère les styles de carte Thniya (clair/sombre × fr/ar) à partir du générateur officiel Protomaps.
// Sortie : mobile/assets/map/thniya-{light,dark}-{fr,ar}.json
const fs = require("fs");
const path = require("path");
const { layers, namedFlavor } = require("@protomaps/basemaps");

const OUT = process.argv[2];

// Palette claire, douce et lisible : la carte est un fond, les lignes de transport sont la vedette.
const light = {
  ...namedFlavor("light"),
  background: "#EEF1F2", earth: "#F5F3EF",
  park_a: "#E1EFDC", park_b: "#CFE7C9", wood_a: "#E1EFDC", wood_b: "#CFE7C9",
  scrub_a: "#E6F0DF", scrub_b: "#D6EACF", hospital: "#F6E6E6", school: "#F1ECE4",
  industrial: "#ECEEF0", pedestrian: "#F0EDE6", sand: "#F3EEDF", beach: "#F6EED7",
  aerodrome: "#E9EBEE", runway: "#DDE1E6", zoo: "#E1EFDC", military: "#ECECEC",
  water: "#BFE1EC", buildings: "#E8E4DE", pier: "#E8E4DE", glacier: "#F2F2F2",
  minor_service: "#FFFFFF", minor_a: "#FFFFFF", minor_b: "#FFFFFF", other: "#FFFFFF",
  link: "#FFFFFF", major: "#FFFFFF", highway: "#FFF6DC",
  minor_service_casing: "#E4E0DA", minor_casing: "#E4E0DA", link_casing: "#E0DBD3",
  major_casing_early: "#DED8CF", major_casing_late: "#DED8CF",
  highway_casing_early: "#EBDDB3", highway_casing_late: "#EBDDB3",
  bridges_minor: "#FFFFFF", bridges_link: "#FFFFFF", bridges_major: "#FFFFFF", bridges_highway: "#FFF6DC",
  bridges_other: "#FFFFFF",
  railway: "#B5B0A8", boundaries: "#C9C2D6",
  roads_label_minor: "#8A9095", roads_label_minor_halo: "#FFFFFF",
  roads_label_major: "#6F767C", roads_label_major_halo: "#FFFFFF",
  ocean_label: "#5E93A8", subplace_label: "#8A9298", subplace_label_halo: "#F5F3EF",
  city_label: "#3B4247", city_label_halo: "#F5F3EF", state_label: "#A9AFB4",
  state_label_halo: "#F5F3EF", country_label: "#9AA1A6", address_label: "#9AA1A6",
  address_label_halo: "#FFFFFF",
};

const dark = {
  ...namedFlavor("dark"),
  background: "#0E1215", earth: "#161B1F",
  park_a: "#18261E", park_b: "#1C2E23", wood_a: "#18261E", wood_b: "#1C2E23",
  water: "#0E2933", buildings: "#20262B", pier: "#20262B",
  minor_service: "#262D33", minor_a: "#262D33", minor_b: "#262D33", other: "#262D33",
  link: "#2C343A", major: "#313A41", highway: "#3A3A30",
  minor_casing: "#1B2025", major_casing_early: "#1B2025", major_casing_late: "#1B2025",
  highway_casing_early: "#26261F", highway_casing_late: "#26261F",
  railway: "#4A5258", boundaries: "#4A4560",
  roads_label_minor: "#7E878E", roads_label_minor_halo: "#161B1F",
  roads_label_major: "#98A1A8", roads_label_major_halo: "#161B1F",
  city_label: "#D5DADE", city_label_halo: "#161B1F", subplace_label: "#8E979E",
  subplace_label_halo: "#161B1F", ocean_label: "#5E8FA0",
};

// Tous les libellés en Readex Pro (police de l'app, latin + arabe), rendus par Flutter.
function useAppFont(node) {
  if (Array.isArray(node)) return node.map(useAppFont);
  if (node && typeof node === "object") {
    const out = {};
    for (const [k, v] of Object.entries(node)) {
      out[k] = k === "text-font" ? ["ReadexPro"] : useAppFont(v);
    }
    return out;
  }
  return node;
}

// Pas d'icônes de POI (pas de sprite) : la carte reste sobre, nos arrêts sont dessinés par l'app.
const keep = (l) => !(l.layout && l.layout["icon-image"]) && l.id !== "pois";

// Zoom minimal des couches coûteuses : à l'échelle du pays (zooms 9-10), une tuile Protomaps porte des milliers de
// polygones (occupation du sol, zones) et de lignes (limites administratives, petites routes) qu'on ne distingue pas
// à l'écran, mais que l'app doit décoder et dessiner — la carte de toute la Tunisie restait vide plusieurs minutes.
const MIN_ZOOM = [
  [/^buildings$/, 14],
  [/^(roads_(tunnels_)?(minor|other|link)|roads_minor_service|roads_pier)/, 12],
  [/^places_subplace$/, 12],
  [/^(landcover|landuse_|roads_runway|boundaries$)/, 11],
];

function withMinZoom(layer) {
  const rule = MIN_ZOOM.find(([re]) => re.test(layer.id));
  if (!rule) return layer;
  return { ...layer, minzoom: Math.max(layer.minzoom || 0, rule[1]) };
}

for (const [name, flavor] of [["light", light], ["dark", dark]]) {
  for (const lang of ["fr", "ar"]) {
    const style = {
      version: 8,
      name: `thniya-${name}-${lang}`,
      sources: { protomaps: { type: "vector", attribution: "© OpenStreetMap, Protomaps" } },
      layers: useAppFont(layers("protomaps", flavor, { lang }).filter(keep).map(withMinZoom)),
    };
    const file = path.join(OUT, `thniya-${name}-${lang}.json`);
    fs.writeFileSync(file, JSON.stringify(style));
    console.log(file, style.layers.length, "couches");
  }
}
