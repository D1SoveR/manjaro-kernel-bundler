# Maintainer: Mikołaj Banasik <d1sover@gmail.com>

pkgname="manjaro-kernel-bundler"
pkgver=0.0.2
pkgdesc="Script used to create single-file kernel bundles (for direct booting and Secure Boot) on Manjaro"
arch=("any")
license=("custom:Public Domain")
depends=("python")
provides=("$pkgname")
conflicts=("$pkgname")

source=("git+git://github.com/D1SoveR/$pkgname.git#tag=v$pkgver")
md5sums=("SKIP")

pkgver() {
	cd "$srcdir/$pkgname"
	local version="$(git describe --tags)"
	echo ${version#v}
}

package() {

	# Install the actual package
	python setup.py install --prefix=/usr --root="$pkgdir" --optimize=1

	# Install the UNLICENSE because Manjaro has no pre-defined license for Public Domain
    install -D -m644 "$srcdir/$pkgname/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

}