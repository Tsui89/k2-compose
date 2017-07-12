cs delete -a
cs run -a

cs delete -a
cs run -s broker
cs run -a --ignore-deps

cs delete -a
cs run -s broker --ignore-deps
cs run -a
