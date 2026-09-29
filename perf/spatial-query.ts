import http from "k6/http";
import { sleep } from "k6"


function randomFloat(min: number, max: number): number {
    return (Math.random() * (max - min) + min)
}

function buildRandomQuery(): string {
    const params = {
        pc_south: randomFloat(51, 52),
        pc_west: randomFloat(-2, -3),
        pc_north: randomFloat(51, 52),
        pc_east: randomFloat(-2, -3),
        pc_lat: randomFloat(51, 52),
        pc_lon: randomFloat(-2, -3),
        map_south: randomFloat(51, 52),
        map_west: randomFloat(-2, -3),
        map_north: randomFloat(51, 52),
        map_east: randomFloat(-2, -3),
        ct: 0
    };

    return Object.entries(params).map(([key, val]) => `${key}=${val}`).join("&");
}

export default function () {
    const url = `${__ENV.BASE_URL}/api/spatial-query?${buildRandomQuery()}`

    http.get(url);
    sleep(randomFloat(0.5, 3));
}

export function handleSummary(data: any): Record<string, string> {
    const outputFile = `metrics/spatial-query.vu${__ENV.K6_VUS}-dur${__ENV.K6_DURATION}.json`
    let result: Record<string, string> = {};

    result[outputFile] = JSON.stringify(data);

    return result;
}