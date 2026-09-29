import http from "k6/http";
import { sleep } from "k6"

function randomFloat(min: number, max: number): number {
    return (Math.random() * (max - min) + min)
}

const BLOBS = [
    "inward/AB1.json",
    "inward/AB10.json",
    "inward/B1.json",
    "inward/B11.json",
    "inward/B18.json",
    "inward/B2.json",
    "inward/BL0.json",
    "inward/BL11.json",
    "inward/BT1.json",
    "tiles/providers.pmtiles",
    "outward.json"
];

function getRandomBlob(): string {
    const index = randomFloat(0, BLOBS.length);

    return BLOBS[index];
}

export default function () {
    const url = `${__ENV.BASE_URL}/data/${getRandomBlob()}`;

    http.get(url);
    sleep(randomFloat(0.5, 3));
}

export function handleSummary(data: any): Record<string, string> {
    const outputFile = `metrics/container.vu${__ENV.K6_VUS}-dur${__ENV.K6_DURATION}.json`
    let result: Record<string, string> = {};

    result[outputFile] = JSON.stringify(data);

    return result;
}