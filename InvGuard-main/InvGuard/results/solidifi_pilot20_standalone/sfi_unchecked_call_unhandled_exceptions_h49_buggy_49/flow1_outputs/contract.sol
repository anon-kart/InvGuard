pragma solidity ^0.5.11;

contract Target {

    function my_func_unchk35(address payable dst) public payable{
            dst.send(msg.value);
        }

    function() external payable {}

    function deposit() public payable {}

}
