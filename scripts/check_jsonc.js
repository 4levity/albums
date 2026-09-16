#!/usr/bin/env node
// Validate JSONC files (JSON with comments, as used by VS Code config files
// such as .vscode/launch.json) with the jsonc-parser library.
//
// Usage: node scripts/check_jsonc.js <file> [<file> ...]
"use strict";

const fs = require("node:fs");
const { parse, printParseErrorCode } = require("jsonc-parser");

// line:column (1-based) of an offset within text
function location(text, offset) {
    const before = text.slice(0, offset);
    const line = before.split("\n").length;
    const column = offset - before.lastIndexOf("\n");
    return `${line}:${column}`;
}

let failed = false;
for (const file of process.argv.slice(2)) {
    let text;
    try {
        text = fs.readFileSync(file, "utf8");
    } catch (error) {
        console.error(`${file}: ${error.message}`);
        failed = true;
        continue;
    }
    const errors = [];
    parse(text, errors, { allowTrailingComma: true });
    for (const error of errors) {
        console.error(`${file}:${location(text, error.offset)}: ${printParseErrorCode(error.error)}`);
        failed = true;
    }
}
process.exit(failed ? 1 : 0);
