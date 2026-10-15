const [major, minor] = process.versions.node.split(".").map(Number);
if (major < 22 || (major === 22 && minor < 12)) {
  console.error(
    `VFXAI needs Node.js 22.12 or newer. Found ${process.version}. Install a current Node.js LTS, then reopen this launcher.`,
  );
  process.exit(1);
}
