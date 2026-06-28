Name:           howdy-island
Version:        0.1.0
Release:        1%{?dist}
Summary:        Dynamic Island-style on-screen indicator for Howdy face authentication

License:        GPL-3.0-or-later
URL:            https://github.com/sijuz/howdy-island
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  systemd-rpm-macros

Requires:       python3
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk3
Requires:       gtk-layer-shell
# Howdy provides the face authentication this indicator visualises. It is a
# weak dependency so the package stays installable even where Howdy is shipped
# from a different repository.
Recommends:     howdy

%description
howdy-island shows a Dynamic Island-style overlay at the top-center of the
screen reflecting Howdy face-authentication state (scanning / recognized /
failed) for in-session prompts such as sudo and polkit. It is implemented with
GTK 3 and gtk-layer-shell so the surface floats as a Wayland layer-shell
overlay.

%prep
%autosetup -n %{name}-%{version}

%build
# Pure-Python application: nothing to compile.

%install
# Application tree.
install -d %{buildroot}%{_prefix}/lib/%{name}
cp -a src/howdy_island %{buildroot}%{_prefix}/lib/%{name}/howdy_island
find %{buildroot}%{_prefix}/lib/%{name} -name '__pycache__' -type d -prune -exec rm -rf {} +

# Launcher on PATH.
install -Dm0755 packaging/%{name}.launcher %{buildroot}%{_bindir}/%{name}

# systemd user unit.
install -Dm0644 packaging/%{name}.service %{buildroot}%{_userunitdir}/%{name}.service

# Default theme template.
install -Dm0644 data/style.css %{buildroot}%{_datadir}/%{name}/style.css

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{_prefix}/lib/%{name}
%{_userunitdir}/%{name}.service
%{_datadir}/%{name}/style.css

%post
%systemd_user_post %{name}.service

%preun
%systemd_user_preun %{name}.service

%postun
%systemd_user_postun %{name}.service

%changelog
* Sun Jun 28 2026 sijuz <noreply@users.noreply.github.com> - 0.1.0-1
- Initial package.
