# Bitcoinアービトラージシステム
## ■概要
2つのビットコイン取引所間で、価格差が発生した場合に、自動的に安い取引所で買って<br>
高い取引所で売ることにより差額を利益として蓄積していくシステム。


## ■実現方式
実際にビットコインでアービトラージ取引をした場合に、安い取引所で買って高い取引所で<br>
売ろうとすると、買った取引所から、売ろうとしている取引所へのビットコインの送金が<br>
必要となる。<br><br>
ビットコインの送金には数分から数十分程度かかるため、その間に価格が動いた場合には<br>
損失が発生してしまう可能性がある。<br><br>
このため、事前に一定程度のビットコインと現金をそれぞれの取引所に事前に置いておく。<br>
そして、差額が発生した場合は、プールしているビットコインと現金の範囲内で取引を<br>
行う。それにより、タイムラグによる損失を防ぐ。<br>
実際に取引をすると、ビットコインの合計は変わらず(実際には手数料分ずつ少なくなる）、<br>
現金の合計が少しずつ増えていく。<br><br>
それと同時に一方の取引所にビットコインがたまり、もう一方の取引所に現金が偏る<br>
状態になっていく。<br><br>
一定程度の偏りが生じた場合は、取引所間の価格差が反転するまで待ち、反転した<br>
タイミングで初期状態（ビットコイン、現金半々くらい）になるまで取引を繰り返す。<br>
以上の処理を繰り返すことにより利益を積み重ねていく。<br>

<br><br>
![arbitrage](https://user-images.githubusercontent.com/8347332/118396058-9fef4e00-b688-11eb-8e9c-ce0abf9afc62.png)
