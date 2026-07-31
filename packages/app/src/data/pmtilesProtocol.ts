import { Protocol } from "pmtiles";
import maplibregl from "maplibre-gl";

let initialized = false;
export function initPmtilesProtocol() {
  if (initialized) return;
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  initialized = true;
}
