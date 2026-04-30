{
  description = "Development shell for declarative nix environment";

  inputs.nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";

  outputs = {self, nixpkgs}: let
    genSystems = nixpkgs.lib.genAttrs [
      "x86_64-linux"
      "x86_64-darwin"
      "aarch64-linux"
      "aarch64-darwin"
    ];
     setPkgs = system: import nixpkgs {inherit system;};

    allSystems = f: genSystems (system:
    let
      pkgs = setPkgs system;
    in f system pkgs);
  in {
    devShells = allSystems (system: pkgs: {
      default = let 
        pyEnv = (pkgs.python3.withPackages (ps: [
          ps.flask
          ps.flask-socketio
          ps.opencv-python
          ps.serialio
        ]));
      in pkgs.mkShell {
        nativeBuildInputs = with pkgs; [
          pyEnv
          opencv
          platformio
        ];
      };
    });
  };
}
