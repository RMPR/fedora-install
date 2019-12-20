#!/bin/bash

if [ $(id -u) = 0 ]; then
   echo "This script must not be run as root!"
   echo "You may need to enter your password multiple times!"
   exit 1
fi


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

sudo dnf install -y https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm

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
@base-x `#Base X11` \
gnome-shell `#Gnome obviously` \
gnome-terminal `#No terminal no life` \
git `#VCS done right` \
htop `#Cli process monitor` \
python3-devel `#Python Development Gear` \
python3-neovim `#Python Neovim Libs` \
adobe-source-code-pro-fonts `#The most beautiful monospace font around` \
neovim `#the better vim` \
tig `#cli git tool` \
vim-enhanced `#full vim` \
gnome-tweaks `#Graphical tweaking of Gnome`

###
# Tell Systemd to boot into Gnome Display Manager
###
sudo systemctl set-default graphical.target

###
# These will be more used in the future by some maintainers
# Reenabling them just to make sure.
###

sudo sed -i '0,/enabled=0/s/enabled=0/enabled=1/g' /etc/yum.repos.d/fedora-updates-modular.repo
sudo sed -i '0,/enabled=0/s/enabled=0/enabled=1/g' /etc/yum.repos.d/fedora-modular.repo

#The user needs to reboot to apply all changes.
echo "Please Reboot" && exit 0

