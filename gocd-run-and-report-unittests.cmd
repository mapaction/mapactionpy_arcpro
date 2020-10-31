pushd mapy-arcpro
"../env/Scripts/python.exe" -m coverage run --include="./*" -m xmlrunner discover mapactionpy_arcpro/tests -o "../junit-reports"
"../env/Scripts/python.exe" -m coveralls
popd
