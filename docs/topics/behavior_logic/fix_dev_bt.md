## Fix Development Behavior {#sec:fix_dev_bt}

The Fix Development Behavior Tree is shown in Figure
[\[fig:bt_fix_development\]](#fig:bt_fix_development){reference-type="ref"
reference="fig:bt_fix_development"}. Fix development is relegated to the
Vendor role, so Non-Vendors just return *Success* since they have
nothing further to do. For Vendors, if a fix is ready (i.e., the case is
in $q^{cs} \in VF\cdot\cdot\cdot\cdot$), the tree returns *Success*. Otherwise,
engaged Vendors ($q^{rm} \in A$) can create fixes, set
$q^{cs} \in Vfd\cdot\cdot\cdot \xrightarrow{\mathbf{F}} VFd\cdot\cdot\cdot$ and emit
$CF$ upon completion.
