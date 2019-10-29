#!/usr/bin/python3
# -*- encoding: utf-8 -*-
# part of https://github.com/WolfgangFahl/play-chess-with-a-webcam
from webchesscam import WebChessCamArgs

def test_WebChessCamArgs():
    argv=["--port=5004","--rotation=90","--debug","--warp","[[1408, 270], [1136, 1049], [236, 667]]"]
    args=WebChessCamArgs(argv).args
    assert args.rotation==90
    assert args.port==5004
    assert args.debug
    expected=[[1408, 270], [1136, 1049], [236, 667]]
    assert args.warpPointList==expected

# https://stackoverflow.com/questions/1894269/convert-string-representation-of-list-to-list
def test_StringRepresentationOfList():
    import ast
    warpPointList=ast.literal_eval("[[1408, 270], [1136, 1049], [236, 667]]")
    expected=[[1408, 270], [1136, 1049], [236, 667]]
    assert warpPointList==expected


if __name__ == '__main__':
  test_StringRepresentationOfList()
  test_WebChessCamArgs()
