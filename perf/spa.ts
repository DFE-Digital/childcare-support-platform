import http from "k6/http";
import { sleep } from "k6"

function randomFloat(min: number, max: number): number {
    return (Math.random() * (max - min) + min)
}

const PAGES = ["", "support", "costs", "providers"];

function getRandomPage(): string {
    const index = randomFloat(0, PAGES.length);

    return PAGES[index];
}

export default function () {
    const url = `${__ENV.BASE_URL}/${getRandomPage()}`;

    http.get(url);
    sleep(randomFloat(0.5, 3));
}

export function handleSummary(data: any): Record<string, string> {
    const outputFile = `metrics/spa.vu${__ENV.K6_VUS}-dur${__ENV.K6_DURATION}.json`
    let result: Record<string, string> = {};

    result[outputFile] = JSON.stringify(data);

    return result;
}