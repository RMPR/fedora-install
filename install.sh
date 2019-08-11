#!/bin/bash
set -euo pipefail

if [ $(id -u) = 0 ]; then
   echo "This script changes your users gsettings and should thus not be run as root!"
   echo "You may need to enter your password multiple times!"
   exit 1
fi


while test $# -gt 0
do
    case "$1" in
        --nonfree)
			echo "Nonfree Additions will be added"
			NONFREE=true
            ;;
        --steam)
#			echo "Adding Steam as flatpak to avoid fedora lib misaligment issues for games"
#			STEAMFLAT=true
#            ;;
    esac
    shift
done


###
# Optionally clean all dnf temporary files
###

sudo dnf clean all

###
# RpmFusion Free Repo
# This is holding only open source, vetted applications - fedora just cant legally distribute them themselves thanks to
# Software patents
###

sudo dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm

###
# RpmFusion NonFree Repo
# This includes Nvidia Drivers and more
###

if [ ! -z "$NONFREE" ]; then
	sudo dnf install -y https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
fi


###
# Disable the Modular Repos
# So far they are pretty empty, and sadly can muck with --best updates
# Reenabling them at the end for future use
###

sudo sed -i 's/enabled=1/enabled=0/g' /etc/yum.repos.d/fedora-updates-modular.repo
sudo sed -i 's/enabled=1/enabled=0/g' /etc/yum.repos.d/fedora-modular.repo


###
# Force update the whole system to the latest and greatest
###

sudo dnf upgrade --best --allowerasing --refresh -y
# And also remove any packages without a source backing them
# If you come from the Fedora 31 Future i'll check if this is still optimal before F31 comes out.
sudo dnf distro-sync -y

###
# Install base packages and applications
###

sudo dnf install \
-y \
arc-theme `#A more comfortable GTK/Gnome-Shell Theme` \
breeze-cursor-theme `#A more comfortable Cursor Theme from KDE` \
chromium-vaapi `#Comes with hardware acceleration and all Codecs` \
darktable `#Easy RAW Editor` \
exfat-utils `#Allows managing exfat (android sd cards and co)` \
ffmpeg `#Adds Codec Support to Firefox, and in general` \
file-roller-nautilus `#More Archives supported in nautilus` \
fuse-exfat `#Allows mounting exfat` \
fuse-sshfs `#Allows mounting servers via sshfs` \
gimp `#The Image Editing Powerhouse - and its plugins` \
gimp-data-extras \
gimp-dbp \
gimp-dds-plugin \
gimp-elsamuko \
gimp-focusblur-plugin \
gimp-fourier-plugin \
gimpfx-foundry.noarch \
gimp-gap \
gimp-high-pass-filter \
gimp-layer-via-copy-cut \
gimp-lensfun \
gimp-lqr-plugin \
gimp-luminosity-masks \
gimp-paint-studio \
gimp-resynthesizer \
gimp-save-for-web \
gimp-wavelet-decompose \
gimp-wavelet-denoise-plugin \
git `#VCS done right` \
gmic-gimp \
gnome-shell-extension-topicons-plus `#Notification Icons for gnome` \
gnome-shell-extension-user-theme `#Enables theming the gnome shell` \
gnome-tweak-tool `#Your central place to make gnome like you want` \
GREYCstoration-gimp \
gtkhash-nautilus `#To get a file has via gui` \
gvfs-fuse `#gnome<>fuse` \
gvfs-mtp `#gnome<>android` \
gvfs-nfs `#gnome<>ntfs` \
gvfs-smb `#gnome<>samba` \
htop `#Cli process monitor` \
keepassxc  `#Password Manager` \
krita  `#Painting done right keep in mind mypaint and gimp cant work together in current upstream versions - yet` \
libreoffice-gallery-vrt-network-equipment `#Network Icon Preset for LibreOffice` \
lm_sensors `#Show your systems Temparature` \
'mozilla-fira-*' `#A nice font family` \
mpv `#The best media player (with simple gui)` \
mumble `#Talk with your friends` \
nautilus-extensions `#What it says on the tin` \
nautilus-image-converter \
nautilus-search-tool \
NetworkManager-openvpn-gnome `#To enforce that its possible to import .ovpn files in the settings` \
openshot `#Simple Video Editor` \
openssh-askpass `#Base Lib to let applications request ssh pass via gui` \
p7zip `#Archives` \
p7zip-plugins `#Even more of them` \
papirus-icon-theme `#A quite nice icon theme` \
pv `#pipe viewer - see what happens between the | with output | pv | receiver ` \
python3-devel `#Python Development Gear` \
python3-neovim `#Python Neovim Libs` \
rawtherapee `#Professional RAW Editor` \
telegram-desktop `#Chatting, with newer openssl and qt base!` \
tilix `#The best terminal manager i know of` \
tilix-nautilus `#Adds right click open in tilix to nautilus` \
transmission `#Torrent Client` \
tuned `#Tuned can optimize your performance according to metrics. tuned-adm profile powersave can help you on laptops, alot` \
unar `#free rar decompression` \
virt-manager `#A gui to manage virtual machines` \
wavemon `#a cli wifi status tool` \
youtube-dl `#Allows you to download and save youtube videos but also to open their links by dragging them into mpv!` \
ansible `#Awesome to manage multiple machines or define states for systems` \
adobe-source-code-pro-fonts `#The most beautiful monospace font around` \
gitg `#a gui for git, a little slow on larger repos sadly` \
iotop  `#disk usage cli monitor` \
meld `#Quick Diff Tool` \
neovim `#the better vim` \
nethogs `#Whats using all your traffic? Now you know!` \
nload `#Network Load Monitor` \
tig `#cli git tool` \
vim-enhanced `#full vim` \
zsh `#Best shell` \
zsh-syntax-highlighting `#Now with syntax highlighting` \
hexchat `#Irc Client` \
libguestfs-tools `#Resize Vm Images and convert them` \
ncdu `#Directory listing CLI tool. For a gui version take a look at "baobab"` \
###
# Remove some un-needed stuff
###

sudo dnf remove \
-y \
gnome-shell-extension-background-logo `#Tasteful but nah` \
totem `#With mpv installed totem became a little useless` \
chromium `#Using Chromium resets chromium-vaapi so remove it if installed, userprofiles will be kept and can be used in -vaapi` \
flowblade `#Sadly has really outdated mlt dependencies`


###
# Enable some of the goodies, but not all
# Its the users responsibility to choose and enable zsh, with oh-my-zsh for example
# or set a more specific tuned profile
###

sudo systemctl enable --now tuned
sudo tuned-adm profile balanced

#Performance:
#sudo tuned-adm profile desktop

#Virtual Machine Host:
#sudo tuned-adm profile virtual-host

#Virtual Machine Guest:
#sudo tuned-adm profile virtual-guest

#Battery Saving:
sudo tuned-adm profile powersave

# Virtual Machines
sudo systemctl enable --now libvirtd

# Management of local/remote system(s) - available via http://localhost:9090
sudo systemctl enable --now cockpit.socket

###
# Theming and GNOME Options
###


# Tilix Dark Theme
gsettings set com.gexperts.Tilix.Settings theme-variant 'dark'

#Gnome Shell Theming
gsettings set org.gnome.desktop.interface gtk-theme 'Arc-Dark'
gsettings set org.gnome.desktop.interface cursor-theme 'Breeze_Snow'
gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark'
gsettings set org.gnome.shell.extensions.user-theme name 'Arc-Dark-solid'

#Set SCP as Monospace (Code) Font
gsettings set org.gnome.desktop.interface monospace-font-name 'Source Code Pro Semi-Bold 12'

#Set Extensions for gnome
gsettings set org.gnome.shell enabled-extensions "['user-theme@gnome-shell-extensions.gcampax.github.com', 'TopIcons@phocean.net', 'dash-to-dock@micxgx.gmail.com']"

#Better Font Smoothing
gsettings set org.gnome.settings-daemon.plugins.xsettings antialiasing 'rgba'

#Usability Improvements
gsettings set org.gnome.desktop.peripherals.mouse accel-profile 'adaptive'
gsettings set org.gnome.desktop.sound allow-volume-above-100-percent true
gsettings set org.gnome.desktop.calendar show-weekdate true
gsettings set org.gnome.desktop.wm.preferences resize-with-right-button true
gsettings set org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close'
gsettings set org.gnome.shell.overrides workspaces-only-on-primary false

#Dash to Dock Theme
gsettings set org.gnome.shell.extensions.dash-to-dock apply-custom-theme false
gsettings set org.gnome.shell.extensions.dash-to-dock custom-background-color false
gsettings set org.gnome.shell.extensions.dash-to-dock custom-theme-customize-running-dots true
gsettings set org.gnome.shell.extensions.dash-to-dock custom-theme-running-dots-color '#729fcf'
gsettings set org.gnome.shell.extensions.dash-to-dock custom-theme-shrink true
gsettings set org.gnome.shell.extensions.dash-to-dock dock-fixed false
gsettings set org.gnome.shell.extensions.dash-to-dock extend-height true
gsettings set org.gnome.shell.extensions.dash-to-dock force-straight-corner false
gsettings set org.gnome.shell.extensions.dash-to-dock icon-size-fixed true
gsettings set org.gnome.shell.extensions.dash-to-dock intellihide-mode 'ALL_WINDOWS'
gsettings set org.gnome.shell.extensions.dash-to-dock isolate-workspaces true
gsettings set org.gnome.shell.extensions.dash-to-dock show-apps-at-top true
gsettings set org.gnome.shell.extensions.dash-to-dock unity-backlit-items false
gsettings set org.gnome.shell.extensions.dash-to-dock transparency-mode 'FIXED'
gsettings set org.gnome.shell.extensions.dash-to-dock running-indicator-style 'SEGMENTED'
gsettings set org.gnome.shell.extensions.dash-to-dock background-opacity 0.70000000000000000

#This indexer is nice, but can be detrimental for laptop users battery life
gsettings set org.freedesktop.Tracker.Miner.Files index-on-battery false
gsettings set org.freedesktop.Tracker.Miner.Files index-on-battery-first-time false
gsettings set org.freedesktop.Tracker.Miner.Files throttle 15

#Nautilus (File Manager) Usability
gsettings set org.gnome.nautilus.icon-view default-zoom-level 'standard'
gsettings set org.gnome.nautilus.preferences executable-text-activation 'ask'
gsettings set org.gtk.Settings.FileChooser sort-directories-first true
gsettings set org.gnome.nautilus.list-view use-tree-view true



# Steam games (32bit) have issues with the too new 32bit compat libs in fedora
# Flatpak is the better option here
if [ ! -z "$STEAMFLAT" ]; then
	sudo dnf install -y flatpak
	sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
	# flatpak -y install flathub com.valvesoftware.Steam
	# Installed but not displayed? Check with: flatpak run com.valvesoftware.Steam
fi


###
# These will be more used in the future by some maintainers
# Reenabling them just to make sure.
###

sudo sed -i '0,/enabled=0/s/enabled=0/enabled=1/g' /etc/yum.repos.d/fedora-updates-modular.repo
sudo sed -i '0,/enabled=0/s/enabled=0/enabled=1/g' /etc/yum.repos.d/fedora-modular.repo

# Use lightdm instead of gdm
sudo dnf install lightdm lightdm-gtk
sudo systemctl disable gdm.service
sudo systemctl enable lightdm.service

# Enable ssh
systemctl start sshd
systemctl enable sshd

# sway specific section
sudo dnf copr enable gumieri/sway
sudo dnf install \
    -y \
    mako \
    sway \
    swaylock \
    waybar \
    playerctl \
    jq \
    libsigc++ \
    pavucontrol \
    sway-debugsource \
    xdotool \

#Fixing some errors on journalctl from sway:

sudo dnf install \
-y \
sway-debugsource \
"libappindicator-*"

# Miscalleneous

# don't forget to enable mouse goodies
chsh zsh
#The user needs to reboot to apply all changes.
echo "Please Reboot" && exit 0
