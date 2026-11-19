"use strict";

const chart = document.querySelector("#chart-plot");
const contactButton = document.querySelector("#chart-contact");
const sketchKey = document.querySelector("#chart-sketch-key");
const form = document.querySelector("#order-form");
const fields = form.querySelector(".order-fields");
const review = document.querySelector("#review-order");
const submit = document.querySelector("#order-submit");
const statusLine = document.querySelector("#desk-status");
const bookStatus = document.querySelector("#book-status");
const suggestedArea = form.elements.area.value;
const contact = [153 + 20 / 60, -12 - 40 / 60];
const fleets = [
    { name: "TF 17", point: [155.5, -15.2] },
    { name: "TF 11", point: [157.5, -16.5] },
];

let geography;
let activeDocument;
let deskTrigger;
let hasSuggestion = false;
let orderStage = "draft";

function svgElement(tag, attributes, text) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [name, value] of Object.entries(attributes)) {
        element.setAttribute(name, value);
    }
    if (text !== undefined) element.textContent = text;
    return element;
}

function drawChart() {
    if (!geography) return;
    const { clientWidth: width, clientHeight: height } = chart;
    if (!width || !height) return;
    chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
    chart.replaceChildren();
    const longitudeSpan = 28;
    const latitudeSpan = Math.max(16.5, longitudeSpan * height / width);
    const project = ([lon, lat]) => [
        width * (.5 + (lon - 155.5) / longitudeSpan),
        height * (.5 - (lat + 14.7) / latitudeSpan),
    ];

    for (let lon = 142; lon <= 169; lon += 1) {
        const [left] = project([lon, 0]);
        const major = lon % 5 === 0;
        chart.append(svgElement("line", {
            class: major ? "grid-line major" : "grid-line", x1: left, x2: left, y1: 0, y2: height,
        }));
        if (major) chart.append(svgElement("text", { class: "grid-label", x: left + 4, y: height - 8 }, `${lon}°E`));
    }
    for (let lat = -28; lat <= -2; lat += 1) {
        const [, top] = project([0, lat]);
        const major = lat % 5 === 0;
        chart.append(svgElement("line", {
            class: major ? "grid-line major" : "grid-line", x1: 0, x2: width, y1: top, y2: top,
        }));
        if (major) chart.append(svgElement("text", { class: "grid-label", x: 5, y: top - 4 }, `${-lat}°S`));
    }

    const geometryClasses = { land: "land", islet: "land", reef: "reef", depth_contour: "depth" };
    for (const feature of geography.features) {
        const style = geometryClasses[feature.properties.class];
        if (!style) continue;
        const { type, coordinates } = feature.geometry;
        if (type !== "Polygon" && type !== "LineString") continue;
        const paths = type === "Polygon" ? coordinates : [coordinates];
        const path = paths.map(points => `M${points.map(project).join(" L")}${type === "Polygon" ? " Z" : ""}`);
        chart.append(svgElement("path", { class: style, d: path.join(" "), "fill-rule": "evenodd" }));
    }
    for (const { properties, geometry } of geography.features) {
        if (properties.class !== "label" || properties.role === "coord" || geometry.type !== "Point") continue;
        const [left, top] = project(geometry.coordinates);
        if (top < 0 || top > height || left < 0 || left > width) continue;
        const style = properties.text === "CORAL SEA" ? "map-name sea" : "map-name";
        const label = svgElement("text", { class: style, x: left, y: Math.max(13, top) }, properties.text);
        chart.append(label);
        label.setAttribute("x", Math.max(8, Math.min(left, width - label.getComputedTextLength() - 8)));
    }
    const showSketch = hasSuggestion && form.elements.area.value === suggestedArea && orderStage !== "signed";
    sketchKey.hidden = !showSketch;
    if (showSketch) {
        const origin = form.elements.unit.selectedIndex === 1 ? fleets[1].point : fleets[0].point;
        const points = [origin, [151.6, -13.5], [152.35, -11.75], [154.3, -12.15], origin];
        chart.append(svgElement("path", { class: "sketch", d: `M${points.map(project).join(" L")} Z` }));
    }
    for (const fleet of fleets) {
        const [left, top] = project(fleet.point);
        chart.append(
            svgElement("rect", {
                class: "friendly", x: left - 5, y: top - 5, width: 10, height: 10,
                transform: `rotate(45 ${left} ${top})`,
            }),
            svgElement("text", { class: "fleet-label", x: left + 12, y: top + 4 }, fleet.name),
        );
    }
    const [left, top] = project(contact);
    contactButton.style.left = `${left}px`;
    contactButton.style.top = `${top}px`;
    contactButton.hidden = false;
}

function openDocument(trigger) {
    const next = document.getElementById(trigger.dataset.open);
    if (activeDocument) {
        activeDocument.close();
    } else {
        deskTrigger = trigger;
    }
    activeDocument = next;
    next.showModal();
}

for (const dialog of document.querySelectorAll(".document")) {
    dialog.addEventListener("close", () => {
        if (activeDocument !== dialog || dialog.open) return;
        activeDocument = null;
        deskTrigger?.focus();
    });
}

document.addEventListener("click", event => {
    const trigger = event.target.closest("[data-open]");
    if (trigger) {
        if (trigger.id === "draft-order" && orderStage === "draft") {
            hasSuggestion = true;
            document.querySelector("#order-source").textContent = "依据：07:45 情报参谋判断 · 07:42 巡逻来电";
            bookStatus.textContent = "待签发 · 复核侦察";
            drawChart();
        }
        openDocument(trigger);
    }
    if (event.target.closest("[data-close]")) activeDocument?.close();
});

const readButton = document.querySelector("#mark-read");
readButton.addEventListener("click", () => {
    if (readButton.getAttribute("aria-disabled") === "true") return;
    document.querySelector("#mail-status").textContent = "已读";
    readButton.textContent = "已标为已读";
    readButton.setAttribute("aria-disabled", "true");
    statusLine.textContent = "07:42 来电已阅。";
});

form.addEventListener("input", drawChart);
form.addEventListener("submit", event => {
    event.preventDefault();
    if (orderStage === "signed") return;
    if (orderStage === "draft") {
        const values = document.querySelector("#review-values");
        values.replaceChildren();
        for (const [name, field] of [["受令单位", "unit"], ["搜索区域", "area"], ["任务意图", "intent"]]) {
            const term = document.createElement("dt");
            const detail = document.createElement("dd");
            term.textContent = name;
            detail.textContent = form.elements[field].value;
            values.append(term, detail);
        }
        orderStage = "review";
        fields.hidden = true;
        review.hidden = false;
        submit.textContent = "签发军令（演示）";
        submit.focus();
        return;
    }
    orderStage = "signed";
    document.querySelector("#order-heading").textContent = "作战命令 / SIGNED COPY";
    document.querySelector("#signed-stamp").textContent = "已签发 · 演示";
    bookStatus.textContent = "已签发 · 演示";
    statusLine.textContent = "复核侦察军令已完成演示签发。";
    document.querySelector("#edit-order").hidden = true;
    submit.hidden = true;
    activeDocument?.querySelector("[data-close]").focus();
    drawChart();
});

document.querySelector("#edit-order").addEventListener("click", () => {
    orderStage = "draft";
    fields.hidden = false;
    review.hidden = true;
    submit.textContent = "核对军令 →";
    form.elements.area.focus();
});

new ResizeObserver(drawChart).observe(chart);
fetch("/war-room-preview/geography")
    .then(response => {
        if (!response.ok) throw new Error(`Geography unavailable: ${response.status}`);
        return response.json();
    })
    .then(data => {
        geography = data;
        drawChart();
    })
    .catch(() => {
        document.querySelector("#chart-error").hidden = false;
    });
