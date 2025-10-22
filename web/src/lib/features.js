const runtimeFlags = {};

export function registerFeatures(serverFlags = {}) {
  if (!serverFlags || typeof serverFlags !== "object") return;
  for (const [key, value] of Object.entries(serverFlags)) {
    runtimeFlags[key] = Boolean(value);
  }
}

export function featureEnabled(name) {
  return Boolean(runtimeFlags[name]);
}

export function listEnabled() {
  return { ...runtimeFlags };
}

export function clearFeature(name) {
  if (name in runtimeFlags) {
    delete runtimeFlags[name];
  }
}

export default runtimeFlags;
