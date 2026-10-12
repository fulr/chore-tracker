const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const cardSource = fs.readFileSync(
  path.join(__dirname, "../custom_components/chore_tracker/chore-tracker-card.js"),
  "utf8"
);

test("card script can be loaded more than once without duplicate registration", () => {
  const definitions = new Map();
  const customCards = [];
  const customElements = {
    get: (name) => definitions.get(name),
    define: (name, element) => {
      if (definitions.has(name)) {
        throw new Error(`The name "${name}" has already been used`);
      }
      definitions.set(name, element);
    },
  };
  const context = vm.createContext({
    HTMLElement: class HTMLElement {},
    customElements,
    window: { customCards },
    console: { info() {}, warn() {} },
  });

  // Each module evaluation has its own top-level lexical scope.
  const moduleSource = `(() => {\n${cardSource}\n})();`;
  vm.runInContext(moduleSource, context);
  assert.doesNotThrow(() => vm.runInContext(moduleSource, context));

  assert.deepEqual([...definitions.keys()], [
    "chore-tracker-card",
    "chore-tracker-card-editor",
  ]);
  assert.equal(customCards.length, 1);
  assert.equal(customCards[0].type, "chore-tracker-card");
});
